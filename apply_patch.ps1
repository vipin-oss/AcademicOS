# AcademicOS — root launcher for apply_patch
# Delegates to scripts/windows/apply_patch.ps1 with the project root resolved.
# Usage:  .\apply_patch.ps1 AcademicOS_M11_Patch.zip
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\apply_patch.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
