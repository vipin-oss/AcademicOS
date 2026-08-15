# AcademicOS - development environment reset (Sprint M10.1, final polish)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
# Interactive menu with confirmation before every destructive action:
#   1 Reset frontend (delete node_modules + .next)
#   2 Reset backend  (delete venv/.venv + caches)
#   3 Reset database (drop + recreate the SQLite quickstart DB, or run
#                      alembic downgrade base on PostgreSQL)
#   4 Reset Qdrant   (delete the academicos-qdrant container + volume)
#   5 Reset everything
#
# Usage:  .\reset_academicos.ps1

param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function Write-Step { param([string]$Msg) Write-Host "[reset] $Msg" -ForegroundColor Cyan }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }

function Confirm-Destructive([string]$What) {
    $answer = Read-Host ("Are you sure you want to {0}? (y/N)" -f $What)
    return ($answer.Trim().ToLower() -in @("y", "yes"))
}

function Reset-Frontend {
    Write-Step "Resetting frontend (node_modules + .next)..."
    if (-not (Confirm-Destructive "delete frontend node_modules and .next")) { Write-Warn "Skipped."; return }
    $frontend = Join-Path $ProjectRoot "frontend"
    foreach ($dir in @("node_modules", ".next", "dist", "coverage")) {
        $p = Join-Path $frontend $dir
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force; Write-Step ("Removed {0}" -f $dir) }
    }
    Write-Step "Run: cd frontend && npm install && npm run dev"
}

function Reset-Backend {
    Write-Step "Resetting backend (venv + caches)..."
    if (-not (Confirm-Destructive "delete backend venv and caches")) { Write-Warn "Skipped."; return }
    $backend = Join-Path $ProjectRoot "backend"
    foreach ($dir in @(".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "storage")) {
        $p = Join-Path $backend $dir
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force; Write-Step ("Removed {0}" -f $dir) }
    }
    Write-Step "Run: cd backend && python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
}

function Reset-Database {
    Write-Step "Resetting database..."
    if (-not (Confirm-Destructive "reset the AcademicOS database")) { Write-Warn "Skipped."; return }
    $backend = Join-Path $ProjectRoot "backend"
    Push-Location $backend
    if ($env:DATABASE_URL -like "sqlite*" -or -not $env:DATABASE_URL) {
        $db = Join-Path $backend "academicos.db"
        if (Test-Path -LiteralPath $db) { Remove-Item -LiteralPath $db -Force; Write-Step ("Removed {0}" -f $db) }
        python scripts/init_db.py
        Write-Step "Fresh SQLite database initialised."
    } else {
        python -m alembic downgrade base
        python -m alembic upgrade head
        Write-Step "PostgreSQL reset via alembic (downgrade base -> upgrade head)."
    }
    Pop-Location
}

function Reset-Qdrant {
    Write-Step "Resetting Qdrant..."
    if (-not (Confirm-Destructive "delete the Qdrant container and volume")) { Write-Warn "Skipped."; return }
    $hasDocker = Get-Command docker -ErrorAction SilentlyContinue
    if ($hasDocker) {
        docker rm -f academicos-qdrant *> $null
        docker volume rm academicos_qdrant *> $null
        Write-Step "Qdrant container + volume removed."
    } else {
        Write-Warn "Docker not found - Qdrant left as-is."
    }
}

Write-Host ""
Write-Host "AcademicOS - Development Environment Reset" -ForegroundColor Cyan
Write-Host "  1  Reset frontend"
Write-Host "  2  Reset backend"
Write-Host "  3  Reset database"
Write-Host "  4  Reset Qdrant"
Write-Host "  5  Reset everything"
Write-Host "  0  Cancel"
Write-Host ""
$choice = Read-Host "Select an option"

switch ($choice) {
    "1" { Reset-Frontend }
    "2" { Reset-Backend }
    "3" { Reset-Database }
    "4" { Reset-Qdrant }
    "5" {
        Reset-Frontend
        Reset-Backend
        Reset-Database
        Reset-Qdrant
    }
    default { Write-Warn "Cancelled." }
}
exit 0
