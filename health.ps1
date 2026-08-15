# AcademicOS - root launcher for health
# Delegates to scripts/windows/health_check.ps1 with the project root resolved.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\health_check.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
