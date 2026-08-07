# AcademicOS — root launcher for stop
# Delegates to scripts/windows/stop_academicos.ps1 with the project root resolved.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\stop_academicos.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
