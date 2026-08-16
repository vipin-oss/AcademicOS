# AcademicOS - one-command Windows startup (V3 dev-startup, enhanced)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Brings up the COMPLETE local development environment in one command:
#   PostgreSQL + Docker/Qdrant (optional), Ollama (+ model), backend
#   (uvicorn + migrations), frontend (Next.js dev), with real HTTP
#   readiness checks (not just "process exists") and duplicate-process
#   protection.
#
# Usage (from the repo root or scripts/windows):
#   .\start_academicos.ps1
#   .\start_academicos.ps1 -NoOpenBrowser
#   .\start_academicos.ps1 -SkipDocker -SkipOllama   # backend+frontend only
#
# The companion stop script is stop_academicos.ps1 (stops ONLY the processes
# this script launched; PostgreSQL and pre-existing services are never touched).

param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$NoOpenBrowser,
    [switch]$SkipDocker,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
# Native commands (docker, ollama, npm, python, alembic, ...) report success
# via $LASTEXITCODE, never via a thrown exception. On PowerShell 7.3+ the
# default $PSNativeCommandUseErrorActionPreference=$true turns a native
# command's stderr (e.g. `docker info` when the engine is down) into a
# NativeCommandError that aborts the script under "Stop". Setting it to $false
# keeps failures as clean $LASTEXITCODE checks instead of cryptic exceptions.
# (No-op on PowerShell 5.1.)
$PSNativeCommandUseErrorActionPreference = $false
$BackendPort = 8000
$FrontendDefaultPort = 3000
$QdrantPort = 6333
$OllamaPort = 11434
$OllamaHost = "http://127.0.0.1:11434"
$DefaultOllamaModel = "qwen2.5:1.5b"   # fallback only; the configured model wins

function Write-Step { param([string]$Msg) Write-Host "[start] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  OK   $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  !!   $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host " FAIL  $Msg" -ForegroundColor Red }

$tempRoot = [System.IO.Path]::GetTempPath()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(800, $false)
        return ($ok -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-Http([string]$Uri, [int]$TimeoutSec = 3) {
    try {
        return Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSec
    } catch {
        return $null
    }
}

function Wait-HttpOk([string]$Uri, [int]$Attempts, [int]$SleepSec, [string]$Marker = "") {
    for ($i = 0; $i -lt $Attempts; $i++) {
        $r = Test-Http $Uri
        if ($r -and $r.StatusCode -eq 200) {
            if (-not $Marker -or ($r.Content -match $Marker)) { return $r }
        }
        Start-Sleep -Seconds $SleepSec
    }
    return $null
}

function Get-ListenerPid([int]$Port) {
    # 1. Get-NetTCPConnection (preferred).
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($c -and $c.OwningProcess) { return [int]$c.OwningProcess }
    } catch { }
    # 2. netstat -ano fallback. Get-NetTCPConnection can come back empty in a
    # non-elevated session (or miss certain listeners) even when the port is
    # genuinely serving — netstat reads the connection table through the older,
    # more permissive API and reliably reports the owning PID. This is what
    # makes frontend.pid get the actual node.exe listener PID.
    try {
        $out = netstat -ano 2>$null
        $pid2 = Get-NetstatListenerPid -Port $Port -NetstatLines $out
        if ($pid2 -gt 0) { return [int]$pid2 }
    } catch { }
    return 0
}

# Parse AI_PROVIDERS_JSON out of a backend/.env file (read-only). Returns a
# hashtable @{ ProviderId; BaseUrl; Model } or $null when absent/unparseable.
function Get-ConfiguredProvider([string]$EnvPath) {
    if (-not (Test-Path -LiteralPath $EnvPath)) { return $null }
    $lines = Get-Content -LiteralPath $EnvPath
    foreach ($line in $lines) {
        $t = $line.Trim()
        if ($t.StartsWith("AI_PROVIDERS_JSON=")) {
            $json = $t.Substring("AI_PROVIDERS_JSON=".Length).Trim()
            if ($json.StartsWith('"') -and $json.EndsWith('"')) { $json = $json.Substring(1, $json.Length - 2) }
            try {
                $cfg = $json | ConvertFrom-Json
                if ($cfg -is [System.Array]) { $cfg = $cfg[0] }
                return @{
                    ProviderId = [string]$cfg.provider_id
                    BaseUrl    = [string]$cfg.base_url
                    Model      = [string]$cfg.model
                }
            } catch {
                return $null
            }
        }
    }
    return $null
}

# True when any Ollama tag matches the configured model name (exact, ":latest",
# or a tag string like "qwen2.5:1.5b:latest").
function Test-ModelPresent([string]$Model, $tags) {
    if (-not $tags -or -not $tags.models) { return $false }
    foreach ($m in $tags.models) {
        $name = [string]$m.name
        if ($name -eq $Model) { return $true }
        if ($name -eq "$Model`:latest") { return $true }
        if ($name.StartsWith("$Model`:")) { return $true }
    }
    return $false
}

# Resolve the project root whether run from the root or scripts/windows.
function Resolve-ProjectRoot {
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "backend")) { return $ProjectRoot }
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "..\backend")) { return (Resolve-Path (Join-Path $ProjectRoot "..")).Path }
    Write-Fail "Could not locate the AcademicOS project root (no 'backend' directory found)."
    exit 1
}

$ProjectRoot = Resolve-ProjectRoot
Set-Location $ProjectRoot
$backendDir = Join-Path $ProjectRoot "backend"
$frontendDir = Join-Path $ProjectRoot "frontend"
$runDir = Join-Path $ProjectRoot ".academicos-run"

if (-not (Test-Path -LiteralPath $runDir)) { New-Item -ItemType Directory -Path $runDir | Out-Null }

# Docker Desktop helpers (dot-sourceable + unit-tested). See
# scripts/windows/docker_helpers.ps1 and scripts/windows/tests/docker_helpers.tests.ps1
$dockerHelpers = Join-Path $ProjectRoot "scripts\windows\docker_helpers.ps1"
if (Test-Path -LiteralPath $dockerHelpers) {
    . $dockerHelpers
} else {
    Write-Warn "docker_helpers.ps1 not found - Docker handling will be degraded (Qdrant may be skipped)."
}

$processHelpers = Join-Path $ProjectRoot "scripts\windows\process_helpers.ps1"
if (Test-Path -LiteralPath $processHelpers) {
    . $processHelpers
} else {
    Write-Warn "process_helpers.ps1 not found - frontend launch will fall back to a naive 'npm' launch."
}

# ---------------------------------------------------------------------------
# 0. Repository / environment checks
# ---------------------------------------------------------------------------
Write-Step "0. Environment"
if (-not (Test-Path -LiteralPath $backendDir)) { Write-Fail "backend/ directory missing."; exit 1 }
if (-not (Test-Path -LiteralPath $frontendDir)) { Write-Fail "frontend/ directory missing."; exit 1 }

$pythonExe = "python"
foreach ($venvPy in @(".venv\Scripts\python.exe", "venv\Scripts\python.exe")) {
    $p = Join-Path $backendDir $venvPy
    if (Test-Path -LiteralPath $p) { $pythonExe = $p; break }
}
if (-not (Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
    Write-Fail "Python not found (looked for '$pythonExe'). Install Python 3.11+ and retry."
    exit 1
}
Write-OK ("Python via '{0}'" -f $pythonExe)

$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) { Write-Fail "Node/npm not found. Install Node 18+ LTS and retry."; exit 1 }
Write-OK ("Node {0} / npm {1}" -f (& node --version), (& npm --version))

# ---------------------------------------------------------------------------
# 1. PostgreSQL (preserved from prior startup tooling)
# ---------------------------------------------------------------------------
Write-Step "1. PostgreSQL"
$pgOk = $false
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService) {
    if ($pgService.Status -ne "Running") {
        Write-Step ("Starting PostgreSQL service ({0})..." -f $pgService.Name)
        try { Start-Service -Name $pgService.Name } catch { Write-Warn ("Could not start service: {0}" -f $_.Exception.Message) }
        Start-Sleep -Seconds 3
    }
    if ((Get-Service -Name $pgService.Name).Status -eq "Running") {
        $pgOk = $true
        Write-OK ("PostgreSQL ({0}) running" -f $pgService.Name)
    } else {
        Write-Fail "PostgreSQL could not be started."
        exit 1
    }
} else {
    if (Test-Port 5432) { $pgOk = $true; Write-OK "PostgreSQL reachable on 5432 (docker or local)" }
    else { Write-Warn "PostgreSQL not detected - docker compose db expected; continuing." }
}

# ---------------------------------------------------------------------------
# 2. Docker / Qdrant
#
# Reuse an already-ready daemon; otherwise discover + start Docker Desktop
# (only if not already running) and POLL for the daemon (Docker Desktop can
# take 30-120s to boot the engine, so the first `docker info` failure is
# never treated as fatal).
# ---------------------------------------------------------------------------
$dockerOk = $false
$qdrantOk = $false
$dockerSkipped = $false
if (-not $SkipDocker) {
    Write-Step "2. Docker"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warn "Docker CLI not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ (or use -SkipDocker to skip Docker/Qdrant)."
        $dockerSkipped = $true
    } else {
        if (Test-DockerDaemonReady) {
            $dockerOk = $true
            Write-OK "Docker daemon ready (reused)"
        } else {
            $desktopRunning = Test-DockerDesktopRunning
            $desktopPath = Get-DockerDesktopPath
            $action = Resolve-DockerAction -DaemonReady $false -DesktopRunning $desktopRunning -DesktopPathFound ($null -ne $desktopPath)

            switch ($action) {
                "start" {
                    Write-Step "Docker Desktop not running -> starting"
                    try {
                        Start-Process -FilePath $desktopPath
                    } catch {
                        Write-Fail ("Could not start Docker Desktop: {0}" -f $_.Exception.Message)
                        $dockerSkipped = $true
                    }
                }
                "wait" {
                    Write-Step "Docker Desktop already running -> waiting for daemon"
                }
                "not_found" {
                    Write-Warn "Docker Desktop executable not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ and retry (or use -SkipDocker to skip Docker/Qdrant)."
                    $dockerSkipped = $true
                }
            }

            if (-not $dockerSkipped) {
                Write-Host "  Waiting for Docker daemon..." -NoNewline
                $dockerReady = Wait-DockerDaemon -TimeoutSeconds 180 -PollSeconds 5 -OnTick {
                    param([int]$elapsed)
                    Write-Host "." -NoNewline
                }
                Write-Host ""
                if ($dockerReady) {
                    $dockerOk = $true
                    Write-OK "Docker daemon ready"
                } else {
                    Write-Fail "Docker daemon did not become ready within 180s. Open Docker Desktop and confirm it shows 'Engine running', then re-run .\start_academicos.ps1 (or use -SkipDocker to continue without Docker/Qdrant)."
                    $dockerSkipped = $true
                }
            }
        }

        # Qdrant (only when the daemon is actually usable).
        if ($dockerOk) {
            Write-Step "3. Qdrant"
            if (-not (Test-Port $QdrantPort)) {
                Write-Step "Starting Qdrant container..."
                $existing = docker ps -a --format "{{.Names}}" 2>$null | Select-String -Quiet "academicos-qdrant"
                if ($existing) {
                    docker start academicos-qdrant *> $null
                } else {
                    docker run -d --name academicos-qdrant -p 6333:6333 -v academicos_qdrant:/qdrant/storage qdrant/qdrant:v1.11.0 *> $null
                }
                Start-Sleep -Seconds 5
            }
            if (Test-Port $QdrantPort) { $qdrantOk = $true; Write-OK ("Qdrant reachable on {0}" -f $QdrantPort) }
            else { Write-Warn "Qdrant not reachable - search will run lexical-only." }
        } else {
            Write-Warn "Docker/Qdrant skipped (daemon not ready) - vector search will run lexical-only."
        }
    }
} else {
    Write-Warn "Docker/Qdrant skipped (-SkipDocker)."
}

# ---------------------------------------------------------------------------
# 3. Backend configuration (read-only: never overwrite the user's .env)
# ---------------------------------------------------------------------------
Write-Step "4. Backend configuration"
$envPath = Join-Path $backendDir ".env"
$provider = $null
if (Test-Path -LiteralPath $envPath) {
    $provider = Get-ConfiguredProvider $envPath
    if ($provider) {
        Write-OK ("AI provider '{0}' -> model '{1}' @ {2}" -f $provider.ProviderId, $provider.Model, $provider.BaseUrl)
        if ($provider.BaseUrl -notlike "*127.0.0.1:11434*" -and $provider.BaseUrl -notlike "*localhost:11434*") {
            Write-Warn ("AI provider base_url is '{0}' - expected 'http://127.0.0.1:11434/v1'. Verify it points at your Ollama." -f $provider.BaseUrl)
        }
    } else {
        Write-Warn "backend/.env exists but AI_PROVIDERS_JSON is missing or unparseable - AI will be unconfigured."
    }
} else {
    Write-Warn "backend/.env not found - the backend will boot with defaults (AI disabled). Copy backend/.env.example to backend/.env to configure AI/Ollama."
}
$ollamaModel = if ($provider -and $provider.Model) { $provider.Model } else { $DefaultOllamaModel }

# ---------------------------------------------------------------------------
# 4. Ollama (native Windows install; reuse if already running)
# ---------------------------------------------------------------------------
$ollamaOk = $false
$ollamaOwned = $false
$ollamaPid = 0
if (-not $SkipOllama) {
    Write-Step "5. Ollama"
    $tags = $null
    try { $tags = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -TimeoutSec 3 } catch { $tags = $null }

    if (-not $tags) {
        # Not reachable: try to start it if the CLI/app is installed.
        $ollamaCli = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaCli) {
            Write-Step "Ollama not running - starting 'ollama serve'..."
            $ollamaProc = Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -PassThru
            $ollamaPid = $ollamaProc.Id
            $ollamaOwned = $true
            # Wait for the tags endpoint to come up (model load can be slow).
            for ($i = 0; $i -lt 20; $i++) {
                Start-Sleep -Seconds 2
                try { $tags = Invoke-RestMethod -Uri "$OllamaHost/api/tags" -TimeoutSec 3; break } catch { $tags = $null }
            }
        } else {
            Write-Warn "Ollama not running and 'ollama' CLI not found. Install Ollama from https://ollama.com and ensure it is running, or start it manually, then re-run."
        }
    }

    if ($tags) {
        $ollamaOk = $true
        $modelPresent = Test-ModelPresent $ollamaModel $tags
        if ($modelPresent) {
            Write-OK ("Ollama running, model '{0}' present" -f $ollamaModel)
        } else {
            Write-Warn ("Model '{0}' not found in Ollama." -f $ollamaModel)
            $ollamaCli = Get-Command ollama -ErrorAction SilentlyContinue
            if ($ollamaCli) {
                Write-Step ("Pulling model '{0}' (this can take a while on first run)..." -f $ollamaModel)
                ollama pull $ollamaModel
                if ($LASTEXITCODE -eq 0) { Write-OK ("Model '{0}' pulled" -f $ollamaModel) }
                else { Write-Warn ("ollama pull failed for '{0}' - check the model name and your network." -f $ollamaModel) }
            } else {
                Write-Warn ("Cannot pull - 'ollama' CLI not found. Install it or pull the model manually:  ollama pull {0}" -f $ollamaModel)
            }
        }
    } else {
        Write-Warn ("Ollama is not reachable at {0}. AI features (chat/QA/enrichment/document semantic extraction) will be unavailable until it is running." -f $OllamaHost)
    }
} else {
    Write-Warn "Ollama checks skipped (-SkipOllama)."
}

# Record ownership only if WE started Ollama.
if ($ollamaOwned -and $ollamaPid -gt 0) { Set-Content -LiteralPath (Join-Path $runDir "ollama.pid") -Value $ollamaPid }

# ---------------------------------------------------------------------------
# 5. Dependencies + migrations
# ---------------------------------------------------------------------------
Write-Step "6. Backend dependencies"
Push-Location $backendDir
& $pythonExe -c "import fastapi, sqlalchemy, alembic, uvicorn" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing backend dependencies..."
    & $pythonExe -m pip install -r requirements.txt *> $null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Backend dependency install failed."; Pop-Location; exit 1 }
}
Write-OK "Backend dependencies present"
Pop-Location

Push-Location $frontendDir
if (-not (Test-Path -LiteralPath "node_modules")) {
    Write-Step "Installing frontend dependencies (npm install)..."
    npm install --no-audit --no-fund *> $null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Frontend dependency install failed."; Pop-Location; exit 1 }
}
Write-OK "Frontend dependencies present"
Pop-Location

Write-Step "7. Database migrations"
Push-Location $backendDir
if ($env:DATABASE_URL -like "sqlite*" -or -not $env:DATABASE_URL) {
    & $pythonExe scripts/init_db.py *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "init_db failed - continuing (may already be initialised)." }
    else { Write-OK "SQLite schema up to date" }
} else {
    & $pythonExe -m alembic upgrade head *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "alembic upgrade failed - continuing; verify DATABASE_URL." }
    else { Write-OK "Alembic at head" }
}
Pop-Location

# ---------------------------------------------------------------------------
# 6. Backend (reuse if healthy; otherwise start + real HTTP readiness)
# ---------------------------------------------------------------------------
Write-Step "8. Backend"
$backendPid = 0
$backendOwned = $false
$backendOk = $false
$healthUri = "http://127.0.0.1:$BackendPort/api/v1/health"
$already = Wait-HttpOk $healthUri 2 1 "academicos-api"
if ($already) {
    $backendOk = $true
    Write-OK "Backend already running on $BackendPort (reused; not owned by this run)"
} elseif (Test-Port $BackendPort) {
    Write-Warn "Port $BackendPort is in use by a non-AcademicOS process. The backend was NOT started - free port $BackendPort (or stop the conflicting process) and re-run."
    # Continue with other services; backend will be reported degraded.
} else {
    Push-Location $backendDir
    $logOut = Join-Path $tempRoot "academicos_backend.out.log"
    $logErr = Join-Path $tempRoot "academicos_backend.err.log"
    Start-Process -FilePath $pythonExe -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$BackendPort" -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $logOut -RedirectStandardError $logErr
    Pop-Location
    $r = Wait-HttpOk $healthUri 40 2 "academicos-api"
    if ($r) {
        $backendOk = $true
        $backendPid = Get-ListenerPid $BackendPort
        if ($backendPid -gt 0) { $backendOwned = $true }
        Write-OK ("Backend running on {0} (PID {1})" -f $BackendPort, $backendPid)
    } else {
        Write-Fail ("Backend failed to become healthy (see {0})" -f $logErr)
    }
}
if ($backendOwned -and $backendPid -gt 0) { Set-Content -LiteralPath (Join-Path $runDir "backend.pid") -Value $backendPid }

# ---------------------------------------------------------------------------
# 7. AI health + backend-to-Ollama connectivity (real checks, not "process exists")
# ---------------------------------------------------------------------------
$aiOk = $false
if ($backendOk) {
    Write-Step "9. AI / Ollama connectivity"
    $aiHealth = Test-Http "http://127.0.0.1:$BackendPort/api/v1/ai/health" 5
    if ($aiHealth) {
        try {
            $ai = $aiHealth.Content | ConvertFrom-Json
            if ($ai.default_provider_valid -eq $true -and $ai.providers_configured -ge 1) {
                $aiOk = $true
                Write-OK ("AI configured: provider '{0}', model '{1}'" -f $ai.default_provider, $ai.default_model)
            } else {
                Write-Warn ("AI provider present but not marked valid (status='{0}', providers_configured={1})." -f $ai.status, $ai.providers_configured)
            }
        } catch { Write-Warn "AI health response was not parseable JSON." }
    } else {
        Write-Warn "GET /api/v1/ai/health did not return 200."
    }
    # Live backend->Ollama proof: the startup pre-warm actually generated a token.
    $ready = Test-Http "http://127.0.0.1:$BackendPort/api/v1/health/ready" 5
    if ($ready) {
        try {
            $rd = $ready.Content | ConvertFrom-Json
            $aiCheck = $rd.checks.ai
            if ($aiCheck.facts.model_resident -eq $true) {
                Write-OK ("Backend reached Ollama and loaded model '{0}' ({1}ms warmup)." -f $aiCheck.facts.model, $aiCheck.facts.warmup_ms)
            } else {
                Write-Warn "AI model is not resident - the first request will pay a cold-load cost (or Ollama is unreachable)."
            }
        } catch { Write-Warn "Readiness response was not parseable JSON." }
    }
}

# ---------------------------------------------------------------------------
# 8. Frontend (reuse if healthy; otherwise start + detect the actual port)
# ---------------------------------------------------------------------------
Write-Step "10. Frontend"
$frontendPid = 0
$frontendOwned = $false
$frontendPort = 0
$frontendOk = $false

# Detect the configured dev port (env var / .env.local), else default 3000.
$configuredPort = $FrontendDefaultPort
$frontendEnvLocal = Join-Path $frontendDir ".env.local"
if (Test-Path -LiteralPath $frontendEnvLocal) {
    $portLine = Get-Content -LiteralPath $frontendEnvLocal | Where-Object { $_ -match "^\s*PORT\s*=" } | Select-Object -First 1
    if ($portLine -and $portLine -match "PORT\s*=\s*(\d+)") { $configuredPort = [int]$Matches[1] }
}
if ($env:PORT -and $env:PORT -match "^\d+$") { $configuredPort = [int]$env:PORT }

# Is a healthy AcademicOS frontend already serving on a known port?
# Uses the SAME deterministic probe as the wait loop below (marker-gated, so
# an unrelated HTTP service on the port is never mistaken for the frontend).
for ($p = $FrontendDefaultPort; $p -le ($FrontendDefaultPort + 10); $p++) {
    if (Test-FrontendHttp -Hostname "127.0.0.1" -Port $p -Marker "__next") {
        $frontendPort = $p
        $frontendOk = $true
        Write-OK ("Frontend already running on {0} (reused; not owned by this run)" -f $p)
        break
    }
}

if (-not $frontendOk) {
    $logOut = Join-Path $tempRoot "academicos_frontend.out.log"
    $logErr = Join-Path $tempRoot "academicos_frontend.err.log"
    # Windows-safe launch: resolve npm.cmd and run it via cmd.exe (never
    # `Start-Process -FilePath "npm"`, which fails with "%1 is not a valid
    # Win32 application"). Start-FrontendDevServer restores the caller's
    # working directory even on failure.
    $npmCmd = Resolve-NpmCmd
    $launchAttempted = $false
    if (-not $npmCmd) {
        Write-Fail "npm.cmd not found (npm is required to run the frontend). Install Node 18+ LTS and retry."
    } else {
        try {
            $null = Start-FrontendDevServer -NpmCmd $npmCmd -FrontendDir $frontendDir -Port $configuredPort -Hostname "127.0.0.1" -LogOut $logOut -LogErr $logErr
            $launchAttempted = $true
        } catch {
            Write-Fail ("Frontend launch failed: {0} (see {1})" -f $_.Exception.Message, $logErr)
            $launchAttempted = $false
        }
    }
    # Wait for a Next.js server to come up; detect the actual port (next may
    # auto-increment if the requested one is taken).
    if ($launchAttempted) {
        $readyPort = Wait-FrontendReady -StartPort $configuredPort -PortSpan 10 -Marker "__next" -Attempts 60 -SleepSeconds 2 -Hostname "127.0.0.1"
        if ($readyPort -gt 0) {
            $frontendPort = $readyPort
            $frontendOk = $true
            $frontendPid = Get-ListenerPid $frontendPort
            if ($frontendPid -gt 0) { $frontendOwned = $true }
            Write-OK ("Frontend running on {0} (PID {1})" -f $frontendPort, $frontendPid)
        } else {
            Write-Fail ("Frontend failed to become reachable (see {0})" -f $logErr)
        }
    }
}
if ($frontendOwned -and $frontendPid -gt 0) {
    Set-Content -LiteralPath (Join-Path $runDir "frontend.pid") -Value $frontendPid
    Set-Content -LiteralPath (Join-Path $runDir "frontend.port") -Value $frontendPort
}

# ---------------------------------------------------------------------------
# 9. Browser (only when we started the frontend, to avoid duplicate windows)
# ---------------------------------------------------------------------------
if (-not $NoOpenBrowser -and $frontendOk -and $frontendPort -gt 0) {
    if ($frontendOwned) {
        Start-Process ("http://127.0.0.1:{0}" -f $frontendPort)
        Write-OK ("Opened http://127.0.0.1:{0} in your default browser." -f $frontendPort)
    } else {
        Write-Warn "Frontend was already running - skipping browser open (use -NoOpenBrowser to silence)."
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
$frontendUrl = if ($frontendPort -gt 0) { "http://127.0.0.1:$frontendPort" } else { "http://127.0.0.1:$configuredPort" }
$ready = $backendOk -and $frontendOk
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
if ($ready) { Write-Host "AcademicOS is READY" -ForegroundColor Green }
else { Write-Host "AcademicOS is UP (partial - see warnings above)" -ForegroundColor Yellow }
Write-Host ""
Write-Host ("  Backend:" )
Write-Host ("    http://127.0.0.1:{0}" -f $BackendPort)
Write-Host ("    Health: {0}" -f $(if ($backendOk) { "OK" } else { "NOT READY" }))
Write-Host ("    AI: {0}" -f $(if ($aiOk) { "OK" } else { "see above" }))
Write-Host ""
Write-Host ("  Docker/Qdrant:")
Write-Host ("    Status: {0}" -f $(if ($dockerOk) { "OK (daemon ready)" } elseif ($SkipDocker) { "skipped (-SkipDocker)" } else { "NOT READY (see above)" }))
Write-Host ("    Qdrant: {0}" -f $(if ($qdrantOk) { "OK" } elseif ($SkipDocker -or $dockerSkipped) { "skipped" } else { "not reachable" }))
Write-Host ""
Write-Host ("  Ollama:")
Write-Host ("    http://127.0.0.1:{0}" -f $OllamaPort)
Write-Host ("    Model: {0}" -f $ollamaModel)
Write-Host ("    Status: {0}" -f $(if ($ollamaOk) { "OK" } else { "NOT RUNNING" }))
Write-Host ""
Write-Host ("  Frontend:")
Write-Host ("    {0}" -f $frontendUrl)
Write-Host ("    Status: {0}" -f $(if ($frontendOk) { "OK" } else { "NOT READY" }))
Write-Host ""
if ($frontendOk) {
    Write-Host ("  Open in browser:")
    Write-Host ("    {0}" -f $frontendUrl)
    Write-Host ""
}
Write-Host ("  Stop everything this script started: .\stop_academicos.ps1")
Write-Host "=====================================================" -ForegroundColor Cyan
exit 0
