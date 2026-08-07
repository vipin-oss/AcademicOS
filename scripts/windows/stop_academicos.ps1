# AcademicOS - graceful Windows shutdown (Sprint M10.1, final polish)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
# Stops the backend and frontend processes started by start_academicos.ps1,
# and (optionally) the Docker Qdrant container. PostgreSQL is NEVER touched.
#
# Usage:  .\stop_academicos.ps1 [-KeepQdrant]

param(
    [switch]$KeepQdrant
)

$ErrorActionPreference = "SilentlyContinue"

function Write-Step { param([string]$Msg) Write-Host "[stop] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }

# --- backend (uvicorn on port 8000) -----------------------------------------
Write-Step "Stopping backend..."
$backend = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($backend) {
    $pidToStop = $backend.OwningProcess
    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
    Write-OK ("Backend stopped (PID {0})" -f $pidToStop)
} else {
    Write-Warn "No backend listener found on 8000."
}

# --- frontend (Next.js on port 3000) ----------------------------------------
Write-Step "Stopping frontend..."
$frontend = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($frontend) {
    $pidToStop = $frontend.OwningProcess
    Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
    Write-OK ("Frontend stopped (PID {0})" -f $pidToStop)
} else {
    Write-Warn "No frontend listener found on 3000."
}

# --- optional Qdrant container ----------------------------------------------
if (-not $KeepQdrant) {
    Write-Step "Stopping Qdrant container..."
    $hasDocker = Get-Command docker -ErrorAction SilentlyContinue
    if ($hasDocker) {
        $name = docker ps --format "{{.Names}}" 2>$null | Select-String -Quiet "academicos-qdrant"
        if ($name) {
            docker stop academicos-qdrant *> $null
            Write-OK "Qdrant container stopped"
        } else {
            Write-Warn "Qdrant container not running."
        }
    } else {
        Write-Warn "Docker CLI not found - Qdrant (if any) left as-is."
    }
}

Write-Host ""
Write-Host "AcademicOS stopped. PostgreSQL was left untouched." -ForegroundColor Green
exit 0
