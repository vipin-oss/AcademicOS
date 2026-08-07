# AcademicOS — root launcher for start
# Delegates to scripts/windows/start_academicos.ps1 with the project root resolved.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\start_academicos.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
