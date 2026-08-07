# AcademicOS — health check (Sprint M10.1)
# Prints PASS/FAIL for every component and exits 0 when all required
# components are healthy, 1 otherwise.
#
# Usage:  .\health_check.ps1

param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "SilentlyContinue"
$script:allPass = $true

function Write-Check {
    param([string]$Name, [bool]$Pass, [string]$Detail = "")
    if ($Pass) {
        Write-Host ("  PASS  {0}  {1}" -f $Name, $Detail) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  {0}  {1}" -f $Name, $Detail) -ForegroundColor Red
        $script:allPass = $false
    }
}

function Test-Port([int]$Port) {
    return (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet)
}

if (Test-Path (Join-Path $ProjectRoot "backend")) { $backend = Join-Path $ProjectRoot "backend" } else { $backend = Join-Path $ProjectRoot "..\backend" }
$frontend = Join-Path (Split-Path $backend -Parent) "frontend"

Write-Host "================= AcademicOS HEALTH CHECK =================" -ForegroundColor Cyan

# PostgreSQL
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgService) {
    Write-Check "PostgreSQL service" ($pgService.Status -eq "Running") $pgService.Name
} else {
    Write-Check "PostgreSQL (port 5432)" (Test-Port 5432)
}

# Database connection (backend health implies it; direct check via python)
Push-Location $backend
$dbOk = $false
$url = $env:DATABASE_URL
if (-not $url) { $url = "sqlite:///./academicos.db" }
if ($url -like "sqlite*") {
    python -c "import sqlite3; sqlite3.connect(r'$($url -replace 'sqlite:///','')').execute('select 1')" *> $null
    $dbOk = ($LASTEXITCODE -eq 0)
} else {
    python -c "import sqlalchemy; sqlalchemy.create_engine(r'$url').connect()" *> $null
    $dbOk = ($LASTEXITCODE -eq 0)
}
Write-Check "Database connection" $dbOk
Pop-Location

# Docker
$hasDocker = Get-Command docker -ErrorAction SilentlyContinue
$dockerOk = $false
if ($hasDocker) { docker info *> $null; $dockerOk = ($LASTEXITCODE -eq 0) }
Write-Check "Docker Engine" $dockerOk

# Qdrant
Write-Check "Qdrant (6333)" (Test-Port 6333)

# Backend
$backendOk = $false
if (Test-Port 8000) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 5
        $backendOk = ($r.StatusCode -eq 200)
    } catch { $backendOk = $false }
}
Write-Check "Backend (8000 + /health)" $backendOk

# Frontend
$frontendOk = $false
if (Test-Port 3000) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 5
        $frontendOk = ($r.StatusCode -eq 200 -or $r.StatusCode -eq 307)
    } catch { $frontendOk = $false }
}
Write-Check "Frontend (3000)" $frontendOk

# Storage
$storage = Join-Path $backend "storage"
Write-Check "Storage directory" (Test-Path $storage) "(backend/storage)"

# Alembic version
Push-Location $backend
$alembicOk = $false
$alembicVersion = ""
try {
    $alembicVersion = python -m alembic current 2>$null | Select-Object -Last 1
    $alembicOk = ($LASTEXITCODE -eq 0 -and $alembicVersion -match "0008")
} catch { $alembicOk = $false }
Write-Check "Alembic at head (0008)" $alembicOk $alembicVersion
Pop-Location

# Node modules
Write-Check "Node modules" (Test-Path (Join-Path $frontend "node_modules"))

# Python packages
Push-Location $backend
python -c "import fastapi, sqlalchemy, alembic, uvicorn, qdrant_client" *> $null
Write-Check "Python packages" ($LASTEXITCODE -eq 0)
Pop-Location

Write-Host "===========================================================" -ForegroundColor Cyan
if ($script:allPass) {
    Write-Host "  ALL CHECKS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  SOME CHECKS FAILED — see above." -ForegroundColor Red
    exit 1
}
