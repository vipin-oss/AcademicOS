# AcademicOS - one-command Windows startup (Sprint M10.1, final polish)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
# Verifies/starts PostgreSQL, Docker Desktop + Engine, Qdrant, backend
# deps + migrations, then starts backend + frontend and opens localhost.
#
# Usage:  .\start_academicos.ps1   (from scripts/windows/ or repo root)

param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$NoOpenBrowser,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$BackendPort = 8000
$FrontendPort = 3000
$QdrantPort = 6333

function Write-Step { param([string]$Msg) Write-Host "[start] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "FAIL  $Msg" -ForegroundColor Red }

# Portable temp root (Windows always sets TEMP; fall back for safety).
$tempRoot = [System.IO.Path]::GetTempPath()

function Test-Port([int]$Port) {
    # Fast, reliable TCP probe (works on PS 5.1 and 7; no Test-NetConnection delay).
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(800, $false)
        if ($ok -and $client.Connected) { return $true }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Resolve-ProjectRoot {
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "backend")) { return $ProjectRoot }
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "..\backend")) { return (Resolve-Path (Join-Path $ProjectRoot "..")).Path }
    Write-Fail "Could not locate the AcademicOS project root."
    exit 1
}

$ProjectRoot = Resolve-ProjectRoot
Set-Location $ProjectRoot
$backendDir = Join-Path $ProjectRoot "backend"
$frontendDir = Join-Path $ProjectRoot "frontend"

# ---------------------------------------------------------------- 1. Postgres
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

# ------------------------------------------------------------ 2. Docker
$dockerOk = $false
$qdrantOk = $false
if (-not $SkipDocker) {
    Write-Step "2. Docker"
    $dockerCli = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCli) {
        Write-Warn "Docker CLI not found - skipping Docker/Qdrant container checks."
    } else {
        docker info *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "Docker Engine not running - starting Docker Desktop..."
            $dd = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
            if (-not $dd) {
                $ddPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
                if (Test-Path -LiteralPath $ddPath) { Start-Process $ddPath }
                else { Write-Warn "Docker Desktop not found at default path - start it manually." }
            }
            $tries = 0
            while ($tries -lt 30) {
                Start-Sleep -Seconds 5
                docker info *> $null
                if ($LASTEXITCODE -eq 0) { break }
                $tries++
            }
            if ($LASTEXITCODE -ne 0) { Write-Warn "Docker Engine still not ready - Qdrant may be unavailable." }
            else { $dockerOk = $true; Write-OK "Docker Engine running" }
        } else {
            $dockerOk = $true
            Write-OK "Docker Engine running"
        }

        # -------------------------------------------------------- 3. Qdrant
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
    }
} else {
    Write-Warn "Docker/Qdrant skipped (-SkipDocker)."
}

# ---------------------------------------------------------- 4. dependencies
Write-Step "4. Dependencies"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { Write-Fail "Python not found."; exit 1 }
$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) { Write-Fail "Node/npm not found."; exit 1 }

Push-Location $backendDir
python -c "import fastapi, sqlalchemy, alembic, uvicorn" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing backend dependencies..."
    python -m pip install -r requirements.txt *> $null
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

# ----------------------------------------------------------- 5. migrations
Write-Step "5. Database migrations"
Push-Location $backendDir
if ($env:DATABASE_URL -like "sqlite*") {
    python scripts/init_db.py *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "init_db failed - continuing (may already be initialised)." }
    else { Write-OK "SQLite schema up to date" }
} else {
    python -m alembic upgrade head *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "alembic upgrade failed - continuing; verify DATABASE_URL." }
    else { Write-OK "Alembic at head (0008)" }
}
Pop-Location

# ------------------------------------------------------------- 6. backend
Write-Step "6. Backend"
if (Test-Port $BackendPort) {
    Write-OK ("Backend already running on {0}" -f $BackendPort)
} else {
    Push-Location $backendDir
    $logOut = Join-Path $tempRoot "academicos_backend.out.log"
    $logErr = Join-Path $tempRoot "academicos_backend.err.log"
    Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $logOut -RedirectStandardError $logErr
    Pop-Location
    $tries = 0
    while ($tries -lt 40) {
        Start-Sleep -Seconds 2
        if (Test-Port $BackendPort) { break }
        $tries++
    }
    if (Test-Port $BackendPort) { Write-OK ("Backend running on {0}" -f $BackendPort) }
    else { Write-Fail ("Backend failed to start (see {0})" -f $logErr); exit 1 }
}

# ------------------------------------------------------------ 7. frontend
Write-Step "7. Frontend"
if (Test-Port $FrontendPort) {
    Write-OK ("Frontend already running on {0}" -f $FrontendPort)
} else {
    Push-Location $frontendDir
    $logOut = Join-Path $tempRoot "academicos_frontend.out.log"
    $logErr = Join-Path $tempRoot "academicos_frontend.err.log"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$FrontendPort" -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $logOut -RedirectStandardError $logErr
    Pop-Location
    $tries = 0
    while ($tries -lt 60) {
        Start-Sleep -Seconds 2
        if (Test-Port $FrontendPort) { break }
        $tries++
    }
    if (Test-Port $FrontendPort) { Write-OK ("Frontend running on {0}" -f $FrontendPort) }
    else { Write-Fail ("Frontend failed to start (see {0})" -f $logErr); exit 1 }
}

# ----------------------------------------------------------- 8. open + summary
if (-not $NoOpenBrowser) {
    Start-Process "http://localhost:3000"
}
function Write-SummaryLine {
    param([string]$Name, [bool]$Ok, [string]$Detail = "")
    if ($Ok) { Write-Host ("  [OK] {0}  {1}" -f $Name, $Detail) -ForegroundColor Green }
    else { Write-Host ("  [--] {0}  {1} (see warning above)" -f $Name, $Detail) -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-SummaryLine "PostgreSQL" $pgOk
Write-SummaryLine "Docker" $dockerOk
Write-SummaryLine "Qdrant" $qdrantOk
Write-SummaryLine "Backend  (http://127.0.0.1:8000/api/v1/health)" $true
Write-SummaryLine "Frontend (http://localhost:3000)" $true
Write-Host "=============================================" -ForegroundColor Cyan
if ($pgOk -and $dockerOk -and $qdrantOk) {
    Write-Host "AcademicOS is ready." -ForegroundColor Green
} else {
    Write-Host "AcademicOS is up, but some optional components are degraded - see the warnings above." -ForegroundColor Yellow
}
exit 0
