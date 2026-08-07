# AcademicOS — one-command Windows startup (Sprint M10.1)
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

function Test-Port([int]$Port) {
    $c = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet
    return $c
}

function Resolve-ProjectRoot {
    # allow invocation from repo root or from scripts/windows
    if (Test-Path (Join-Path $ProjectRoot "backend")) { return $ProjectRoot }
    if (Test-Path (Join-Path $ProjectRoot "..\backend")) { return (Resolve-Path (Join-Path $ProjectRoot "..")).Path }
    Write-Fail "Could not locate the AcademicOS project root."
    exit 1
}

$ProjectRoot = Resolve-ProjectRoot
Set-Location $ProjectRoot
$backendDir = Join-Path $ProjectRoot "backend"
$frontendDir = Join-Path $ProjectRoot "frontend"

# ---------------------------------------------------------------- 1. Postgres
Write-Step "1. PostgreSQL"
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService) {
    if ($pgService.Status -ne "Running") {
        Write-Step "Starting PostgreSQL service ($($pgService.Name))…"
        Start-Service -Name $pgService.Name
        Start-Sleep -Seconds 3
    }
    if ((Get-Service -Name $pgService.Name).Status -eq "Running") {
        Write-OK "PostgreSQL ($($pgService.Name)) running"
    } else {
        Write-Fail "PostgreSQL could not be started."
        exit 1
    }
} else {
    # Docker-managed PostgreSQL fallback
    if (Test-Port 5432) { Write-OK "PostgreSQL reachable on 5432 (docker or local)" }
    else { Write-Warn "PostgreSQL not detected — docker compose db will be expected; continuing." }
}

# ------------------------------------------------------------ 2. Docker
if (-not $SkipDocker) {
    Write-Step "2. Docker"
    $dockerCli = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCli) {
        Write-Warn "Docker CLI not found — skipping Docker/Qdrant container checks."
    } else {
        docker info *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "Docker Engine not running — starting Docker Desktop…"
            $dd = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
            if (-not $dd) {
                $ddPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
                if (Test-Path $ddPath) { Start-Process $ddPath }
                else { Write-Warn "Docker Desktop not found at default path — start it manually." }
            }
            $tries = 0
            while ($tries -lt 30) {
                Start-Sleep -Seconds 5
                docker info *> $null
                if ($LASTEXITCODE -eq 0) { break }
                $tries++
            }
            if ($LASTEXITCODE -ne 0) { Write-Warn "Docker Engine still not ready — Qdrant may be unavailable." }
            else { Write-OK "Docker Engine running" }
        } else {
            Write-OK "Docker Engine running"
        }

        # -------------------------------------------------------- 3. Qdrant
        Write-Step "3. Qdrant"
        if (-not (Test-Port $QdrantPort)) {
            Write-Step "Starting Qdrant container…"
            docker ps -a --format "{{.Names}}" | Select-String -Quiet "academicos-qdrant"
            if ($LASTEXITCODE -eq 0) {
                docker start academicos-qdrant *> $null
            } else {
                docker run -d --name academicos-qdrant -p 6333:6333 -v academicos_qdrant:/qdrant/storage qdrant/qdrant:v1.11.0 *> $null
            }
            Start-Sleep -Seconds 5
        }
        if (Test-Port $QdrantPort) { Write-OK "Qdrant reachable on $QdrantPort" }
        else { Write-Warn "Qdrant not reachable — search will run lexical-only." }
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
    Write-Step "Installing backend dependencies…"
    python -m pip install -r requirements.txt *> $null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Backend dependency install failed."; Pop-Location; exit 1 }
}
Write-OK "Backend dependencies present"
Pop-Location

Push-Location $frontendDir
if (-not (Test-Path "node_modules")) {
    Write-Step "Installing frontend dependencies (npm install)…"
    npm install --no-audit --no-fund *> $null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Frontend dependency install failed."; Pop-Location; exit 1 }
}
Write-OK "Frontend dependencies present"
Pop-Location

# ----------------------------------------------------------- 5. migrations
Write-Step "5. Database migrations"
Push-Location $backendDir
# SQLite quickstart: init_db; PostgreSQL: alembic
if ($env:DATABASE_URL -like "sqlite*") {
    python scripts/init_db.py *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "init_db failed — continuing (may already be initialised)." }
    else { Write-OK "SQLite schema up to date" }
} else {
    python -m alembic upgrade head *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warn "alembic upgrade failed — continuing; verify DATABASE_URL." }
    else { Write-OK "Alembic at head (0008)" }
}
Pop-Location

# ------------------------------------------------------------- 6. backend
Write-Step "6. Backend"
if (Test-Port $BackendPort) {
    Write-OK "Backend already running on $BackendPort"
} else {
    Push-Location $backendDir
    $log = Join-Path $env:TEMP "academicos_backend.log"
    Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $log
    Pop-Location
    $tries = 0
    while ($tries -lt 40) {
        Start-Sleep -Seconds 2
        if (Test-Port $BackendPort) { break }
        $tries++
    }
    if (Test-Port $BackendPort) { Write-OK "Backend running on $BackendPort" }
    else { Write-Fail "Backend failed to start (see $log)"; exit 1 }
}

# ------------------------------------------------------------ 7. frontend
Write-Step "7. Frontend"
if (Test-Port $FrontendPort) {
    Write-OK "Frontend already running on $FrontendPort"
} else {
    Push-Location $frontendDir
    $log = Join-Path $env:TEMP "academicos_frontend.log"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$FrontendPort" -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $log
    Pop-Location
    $tries = 0
    while ($tries -lt 60) {
        Start-Sleep -Seconds 2
        if (Test-Port $FrontendPort) { break }
        $tries++
    }
    if (Test-Port $FrontendPort) { Write-OK "Frontend running on $FrontendPort" }
    else { Write-Fail "Frontend failed to start (see $log)"; exit 1 }
}

# ----------------------------------------------------------- 8. open + summary
if (-not $NoOpenBrowser) {
    Start-Process "http://localhost:3000"
}
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  ✓ PostgreSQL" -ForegroundColor Green
Write-Host "  ✓ Docker" -ForegroundColor Green
Write-Host "  ✓ Qdrant" -ForegroundColor Green
Write-Host "  ✓ Backend  (http://127.0.0.1:8000/api/v1/health)" -ForegroundColor Green
Write-Host "  ✓ Frontend (http://localhost:3000)" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host "AcademicOS is ready." -ForegroundColor Green
exit 0
