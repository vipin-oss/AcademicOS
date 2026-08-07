# AcademicOS — environment validation (Sprint M10.1)
# Detects missing tools (Python, Node, npm, Docker, PostgreSQL, Git),
# required ports, and dependencies; prints how to fix each issue.
#
# Usage:  .\validate_environment.ps1

$ErrorActionPreference = "SilentlyContinue"
$script:issues = 0

function Write-Pass { param([string]$Msg) Write-Host ("  PASS  {0}" -f $Msg) -ForegroundColor Green }
function Write-Fail {
    param([string]$Msg, [string]$Fix)
    Write-Host ("  FAIL  {0}" -f $Msg) -ForegroundColor Red
    if ($Fix) { Write-Host ("        fix: {0}" -f $Fix) -ForegroundColor Yellow }
    $script:issues++
}

function Test-Port([int]$Port) {
    return (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet)
}

Write-Host "================= AcademicOS ENVIRONMENT VALIDATION =================" -ForegroundColor Cyan

# Python
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $ver = python --version 2>&1
    Write-Pass "Python — $ver"
    python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" *> $null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Python 3.11+ required (found older)" "Install Python 3.11+ from python.org and re-run" }
} else {
    Write-Fail "Python not found" "Install Python 3.11+ from https://www.python.org/downloads/ (check 'Add to PATH')"
}

# Node / npm
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Pass "Node — $(node --version)"
    if ((node --version) -match "v(1[0-9]|[2-9][0-9])\.") { } else {
        Write-Fail "Node 18+ required" "Install Node LTS from https://nodejs.org/"
    }
} else {
    Write-Fail "Node not found" "Install Node LTS from https://nodejs.org/"
}
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) { Write-Pass "npm — $(npm --version)" }
else { Write-Fail "npm not found" "Install Node (bundles npm)" }

# Docker
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { Write-Pass "Docker Engine running" }
    else { Write-Fail "Docker Engine not running" "Start Docker Desktop: C:\Program Files\Docker\Docker\Docker Desktop.exe" }
} else {
    Write-Fail "Docker not found" "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
}

# PostgreSQL
$pg = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pg) {
    Write-Pass "PostgreSQL service — $($pg.Name)"
} elseif (Test-Port 5432) {
    Write-Pass "PostgreSQL reachable on 5432"
} else {
    Write-Fail "PostgreSQL not detected" "Install PostgreSQL from https://www.postgresql.org/download/windows/ (or use docker compose up -d db)"
}

# Git
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Write-Pass "Git — $(git --version)" }
else { Write-Fail "Git not found" "Install Git from https://git-scm.com/download/win" }

# Required ports
foreach ($port in @(@(8000, "backend"), @(3000, "frontend"), @(6333, "Qdrant"))) {
    if (Test-Port $port[0]) {
        Write-Host ("  INFO  Port {0} ({1}) already in use — expected when running." -f $port[0], $port[1]) -ForegroundColor DarkGray
    } else {
        Write-Pass "Port $($port[0]) ($($port[1])) free"
    }
}

# Backend dependencies
Push-Location (Join-Path (Get-Location) "backend")
python -c "import fastapi, sqlalchemy, alembic, uvicorn, qdrant_client" *> $null
if ($LASTEXITCODE -eq 0) { Write-Pass "Backend Python packages installed" }
else { Write-Fail "Backend Python packages missing" "cd backend && pip install -r requirements.txt" }
Pop-Location

# Frontend dependencies
$frontend = Join-Path (Get-Location) "frontend"
if (Test-Path (Join-Path $frontend "node_modules")) { Write-Pass "Frontend node_modules present" }
else { Write-Fail "Frontend node_modules missing" "cd frontend && npm install" }

Write-Host "=====================================================================" -ForegroundColor Cyan
if ($script:issues -eq 0) {
    Write-Host "  ENVIRONMENT OK — run .\start.ps1" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("  {0} issue(s) found — fix and re-run." -f $script:issues) -ForegroundColor Red
    exit 1
}
