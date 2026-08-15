# AcademicOS - graceful Windows shutdown (V3 dev-startup)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Stops ONLY the backend / frontend / Ollama processes that were LAUNCHED and
# recorded by start_academicos.ps1 (via the PID files in .academicos-run).
# Pre-existing services that were merely REUSED are never touched, and
# PostgreSQL is NEVER touched. Unrelated Python/Node/Ollama processes are
# never killed: each recorded PID is name-verified before termination.
#
# Usage (from the repo root or scripts/windows):
#   .\stop_academicos.ps1
#   .\stop_academicos.ps1 -KeepQdrant    # leave the Qdrant container running

param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$KeepQdrant
)

$ErrorActionPreference = "SilentlyContinue"

function Write-Step { param([string]$Msg) Write-Host "[stop] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  OK   $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  !!   $Msg" -ForegroundColor Yellow }

# Resolve the project root whether run from the root or scripts/windows.
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "backend"))) {
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "..\backend")) {
        $ProjectRoot = (Resolve-Path (Join-Path $ProjectRoot "..")).Path
    }
}
$runDir = Join-Path $ProjectRoot ".academicos-run"

# Process-name allowlist for the things the START script is allowed to own.
$AllowedNames = @("python", "pythonw", "python3", "node", "ollama")

function Stop-Owned([string]$PidFile, [string]$Label) {
    $path = Join-Path $runDir $PidFile
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Warn ("No {0} process recorded (was not started by start_academicos.ps1)." -f $Label)
        return
    }
    $pidValue = (Get-Content -LiteralPath $path | Select-Object -First 1) -as [int]
    Remove-Item -LiteralPath $path -Force
    if (-not $pidValue -or $pidValue -le 0) { Write-Warn ("{0}: invalid PID file content; nothing to stop." -f $Label); return }

    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $proc) { Write-Warn ("{0} process (PID {1}) is no longer running." -f $Label, $pidValue); return }

    # Safety: only terminate processes whose name matches what we are allowed
    # to own. Never kill an unrelated process that happened to reuse the PID.
    if ($proc.ProcessName -notin $AllowedNames) {
        Write-Warn ("Refusing to stop PID {0} ({1}) - not a process AcademicOS owns." -f $pidValue, $proc.ProcessName)
        return
    }

    Write-Step ("Stopping {0} (PID {1}, {2})..." -f $Label, $pidValue, $proc.ProcessName)
    taskkill.exe /T /PID $pidValue /F 2>$null
    if ($LASTEXITCODE -eq 0) { Write-OK ("{0} stopped" -f $Label) }
    else {
        Stop-Process -Id $pidValue -Force
        Write-OK ("{0} stopped (Stop-Process fallback)" -f $Label)
    }
}

Write-Step "Stopping services owned by AcademicOS..."

Stop-Owned "frontend.pid" "Frontend"
Stop-Owned "backend.pid" "Backend"
Stop-Owned "ollama.pid" "Ollama"

# Clean up the (now stale) frontend port record.
$portFile = Join-Path $runDir "frontend.port"
if (Test-Path -LiteralPath $portFile) { Remove-Item -LiteralPath $portFile -Force }

# ---------------------------------------------------------------------------
# Optional: Qdrant container (preserved from prior tooling). PostgreSQL never.
# ---------------------------------------------------------------------------
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
Write-Host "AcademicOS stopped. PostgreSQL and any pre-existing (non-owned) processes were left untouched." -ForegroundColor Green
exit 0
