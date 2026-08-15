# AcademicOS - process-launch helper tests (self-contained; no Pester)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Exercises the Windows frontend-launch helpers in process_helpers.ps1:
#   - npm.cmd resolution (Windows batch shim vs native binary)
#   - cmd.exe launch spec for .cmd shims ("%1 is not a valid Win32 application" fix)
#   - no duplicate frontend process (Resolve-FrontendAction)
#   - working-directory restoration (Start-FrontendDevServer try/finally)
#
# Usage:
#   pwsh -NoProfile -File scripts\windows\tests\process_helpers.tests.ps1
# Exits 0 when all assertions pass, 1 otherwise.

$ErrorActionPreference = "Stop"
$helpers = Join-Path (Split-Path -Parent $PSScriptRoot) "process_helpers.ps1"
. $helpers

$script:Pass = 0
$script:Fail = 0

function Assert-True([bool]$Condition, [string]$Label) {
    if ($Condition) {
        $script:Pass++
        Write-Host ("  PASS  {0}" -f $Label) -ForegroundColor Green
    } else {
        $script:Fail++
        Write-Host ("  FAIL  {0}" -f $Label) -ForegroundColor Red
    }
}

function Assert-Equal($Expected, $Actual, [string]$Label) {
    if ($Expected -eq $Actual) {
        $script:Pass++
        Write-Host ("  PASS  {0}" -f $Label) -ForegroundColor Green
    } else {
        $script:Fail++
        Write-Host ("  FAIL  {0}  (expected '{1}', got '{2}')" -f $Label, $Expected, $Actual) -ForegroundColor Red
    }
}

Write-Host "AcademicOS process-helper tests" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Launch command: Windows .cmd shim -> cmd.exe
# ---------------------------------------------------------------------------
Write-Host "[1] cmd.exe launch spec for a .cmd shim" -ForegroundColor Cyan
$spec = Get-FrontendLaunchCommand -NpmCmd "C:\Program Files\nodejs\npm.cmd" -Port 3000 -Hostname "127.0.0.1"
Assert-True ($null -ne $spec) "returns a spec for a .cmd shim"
Assert-Equal "cmd.exe" $spec.FilePath "FilePath is cmd.exe (never a bare npm.cmd)"
Assert-True ($spec.ArgumentList -match '"[^"]*npm\.cmd"') "shim path is quoted in the argument list"
Assert-True ($spec.ArgumentList -match "run dev -- --hostname 127\.0\.0\.1 --port 3000") "preserves npm run dev + host + port"
Assert-True ($spec.ArgumentList.StartsWith("/d /s /c")) "uses /d /s /c flags"

# ---------------------------------------------------------------------------
# 2. Launch command: native binary (non-Windows) -> direct
# ---------------------------------------------------------------------------
Write-Host "[2] Direct launch spec for a native npm binary" -ForegroundColor Cyan
$spec2 = Get-FrontendLaunchCommand -NpmCmd "/usr/bin/npm" -Port 3000 -Hostname "127.0.0.1"
Assert-True ($null -ne $spec2) "returns a spec for a native binary"
Assert-Equal "/usr/bin/npm" $spec2.FilePath "FilePath is the binary itself"
Assert-Equal "run dev -- --hostname 127.0.0.1 --port 3000" $spec2.ArgumentList "argument list is the npm run dev args"

# ---------------------------------------------------------------------------
# 3. Missing npm -> null spec
# ---------------------------------------------------------------------------
Write-Host "[3] Missing npm -> null" -ForegroundColor Cyan
Assert-True ($null -eq (Get-FrontendLaunchCommand -NpmCmd "" -Port 3000)) "empty npm -> null spec"
Assert-True ($null -eq (Get-FrontendLaunchCommand -NpmCmd $null -Port 3000)) "null npm -> null spec"

# ---------------------------------------------------------------------------
# 4. npm.cmd resolution (Windows shim preferred over a bare 'npm')
# ---------------------------------------------------------------------------
Write-Host "[4] npm.cmd resolution" -ForegroundColor Cyan
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-npmtest-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir | Out-Null
$fakeNpmCmd = Join-Path $tmpDir "npm.cmd"
Set-Content -LiteralPath $fakeNpmCmd -Value "@echo off"
try {
    $prevPath = $env:PATH
    $env:PATH = $tmpDir + [System.IO.Path]::PathSeparator + $prevPath
    $resolved = Resolve-NpmCmd
    Assert-True ($null -ne $resolved) "resolves npm when npm.cmd is on PATH"
    Assert-True ($resolved -like "*.cmd") "resolves to the .cmd shim on Windows-style PATH"
} finally {
    $env:PATH = $prevPath
    Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 5. No duplicate frontend process (decision logic)
# ---------------------------------------------------------------------------
Write-Host "[5] No duplicate frontend process" -ForegroundColor Cyan
Assert-Equal "reuse" (Resolve-FrontendAction -HealthyFrontendDetected $true)  "healthy frontend -> reuse (do NOT start a second)"
Assert-Equal "start" (Resolve-FrontendAction -HealthyFrontendDetected $false) "no healthy frontend -> start"

# ---------------------------------------------------------------------------
# 6. Working-directory restoration (Start-FrontendDevServer try/finally)
# ---------------------------------------------------------------------------
Write-Host "[6] Working-directory restoration" -ForegroundColor Cyan
$tmpWork = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-wdtest-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpWork | Out-Null
$tmpFrontend = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-fe-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpFrontend | Out-Null

# A harmless "npm" stand-in that we can actually Start-Process on both Windows
# and this Linux test host: use the host's `true`/`sh -c` so a real process is
# spawned without side effects. If `true` is unavailable, fall back to `echo`.
$standin = (Get-Command true -ErrorAction SilentlyContinue).Source
if (-not $standin) { $standin = (Get-Command echo -ErrorAction SilentlyContinue).Source }
if (-not $standin) { $standin = (Get-Command sh -ErrorAction SilentlyContinue).Source }

Push-Location $tmpWork
try {
    $before = (Get-Location).Path
    $proc = Start-FrontendDevServer -NpmCmd $standin -FrontendDir $tmpFrontend -Port 3000 -Hostname "127.0.0.1"
    $after = (Get-Location).Path
    Assert-Equal $before $after "caller location restored after launch"
    if ($proc) {
        # Clean up the spawned stand-in process if it is still alive.
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $tmpWork -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmpFrontend -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("RESULT: {0} passed, {1} failed" -f $script:Pass, $script:Fail) -ForegroundColor Cyan
if ($script:Fail -gt 0) { exit 1 } else { exit 0 }
