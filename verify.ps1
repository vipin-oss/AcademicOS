# AcademicOS - root launcher for milestone verification
# Delegates to scripts/windows/verify_milestone.ps1 with the project root resolved.
# Usage:  .\verify.ps1 M1        (add -SkipFlaky to deselect known-flaky tests)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\verify_milestone.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
