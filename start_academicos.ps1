# AcademicOS - canonical one-command startup (repo root).
# Delegates to scripts/windows/start_academicos.ps1 with the project root resolved.
#
# Usage:  .\start_academicos.ps1 [-NoOpenBrowser] [-SkipDocker] [-SkipOllama]
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "scripts\windows\start_academicos.ps1") -ProjectRoot $Root @args
exit $LASTEXITCODE
