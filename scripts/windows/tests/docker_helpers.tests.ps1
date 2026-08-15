# AcademicOS - Docker helper tests (self-contained; no Pester dependency)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Exercises the pure Docker Desktop helpers in docker_helpers.ps1:
#   - Docker already ready                    (Wait-DockerDaemon returns true fast)
#   - Docker initially down then ready        (poll flips a flag)
#   - Docker unavailable after timeout        (Wait-DockerDaemon returns false)
#   - Docker Desktop executable discovery     (Get-DockerDesktopPath)
#   - no duplicate Docker Desktop launch      (Resolve-DockerAction)
#   - docker info exit-code / stderr handling (Invoke-DockerInfo / Test-DockerDaemonReady)
#
# Usage:
#   pwsh -NoProfile -File scripts\windows\tests\docker_helpers.tests.ps1
# Exits 0 when all assertions pass, 1 otherwise.

$ErrorActionPreference = "Stop"
$helpers = Join-Path (Split-Path -Parent $PSScriptRoot) "docker_helpers.ps1"
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

Write-Host "AcademicOS Docker helper tests" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Docker already ready
# ---------------------------------------------------------------------------
Write-Host "[1] Docker already ready" -ForegroundColor Cyan
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$r = Wait-DockerDaemon -Probe { $true } -TimeoutSeconds 10 -PollSeconds 1
$sw.Stop()
Assert-True $r "ready probe returns true immediately"
Assert-True ($sw.Elapsed.TotalSeconds -lt 2) "no needless polling when already ready"

# ---------------------------------------------------------------------------
# 2. Docker initially unavailable, then becomes ready
# ---------------------------------------------------------------------------
Write-Host "[2] Docker initially down, then ready" -ForegroundColor Cyan
$script:ready = $false
$script:ticks = 0
$r = Wait-DockerDaemon -Probe { $script:ready } -TimeoutSeconds 15 -PollSeconds 1 -OnTick {
    param([int]$elapsed)
    $script:ticks++
    if ($script:ticks -eq 1) { $script:ready = $true }   # comes up after one poll
}
Assert-True $r "returns true once the daemon comes up"
Assert-True ($script:ticks -ge 1) "polled at least once before ready"

# ---------------------------------------------------------------------------
# 3. Docker unavailable after timeout
# ---------------------------------------------------------------------------
Write-Host "[3] Docker unavailable after timeout" -ForegroundColor Cyan
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$r = Wait-DockerDaemon -Probe { $false } -TimeoutSeconds 2 -PollSeconds 1
$sw.Stop()
Assert-True (-not $r) "returns false when the daemon never comes up"
Assert-True ($sw.Elapsed.TotalSeconds -ge 1.5) "waited approximately the timeout (not forever)"

# ---------------------------------------------------------------------------
# 4. Docker Desktop executable discovery
# ---------------------------------------------------------------------------
Write-Host "[4] Docker Desktop executable discovery" -ForegroundColor Cyan

# Save + redirect the well-known env vars to an isolated temp tree.
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-ddtest-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$fakeExe = Join-Path $tmp "Docker\Docker\Docker Desktop.exe"
New-Item -ItemType Directory -Path (Split-Path -Parent $fakeExe) -Force | Out-Null
Set-Content -LiteralPath $fakeExe -Value "fake" -ErrorAction SilentlyContinue

$prevPf = $env:ProgramFiles
$prevPf86 = ${env:ProgramFiles(x86)}
$prevLocal = $env:LOCALAPPDATA
try {
    $env:ProgramFiles = $tmp
    ${env:ProgramFiles(x86)} = (Join-Path $tmp "empty-x86")
    $env:LOCALAPPDATA = (Join-Path $tmp "empty-local")

    $found = Get-DockerDesktopPath
    Assert-True ($null -ne $found) "discovers Docker Desktop in Program Files"
    # Platform-agnostic: on Windows the separator is "\", on this Linux test
    # host Join-Path normalizes it to "/" — assert the meaningful parts only.
    Assert-True ((Split-Path -Leaf $found) -eq "Docker Desktop.exe") "returns the executable path"
    Assert-True ($found -like "*Docker*Docker Desktop.exe") "path is under a Docker install folder"

    # not installed anywhere -> $null
    $env:ProgramFiles = (Join-Path $tmp "empty-pf")
    $nullFound = Get-DockerDesktopPath
    Assert-True ($null -eq $nullFound) "returns null when Docker Desktop is not installed"
} finally {
    $env:ProgramFiles = $prevPf
    ${env:ProgramFiles(x86)} = $prevPf86
    $env:LOCALAPPDATA = $prevLocal
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 5. No duplicate Docker Desktop launch (decision logic)
# ---------------------------------------------------------------------------
Write-Host "[5] No duplicate Docker Desktop launch" -ForegroundColor Cyan
Assert-Equal "reuse" (Resolve-DockerAction -DaemonReady $true  -DesktopRunning $false -DesktopPathFound $false) "daemon ready -> reuse (no action)"
Assert-Equal "wait"  (Resolve-DockerAction -DaemonReady $false -DesktopRunning $true  -DesktopPathFound $true)  "desktop running -> wait, do NOT launch a second copy"
Assert-Equal "wait"  (Resolve-DockerAction -DaemonReady $false -DesktopRunning $true  -DesktopPathFound $false) "desktop running -> wait even if path lookup failed"
Assert-Equal "start" (Resolve-DockerAction -DaemonReady $false -DesktopRunning $false -DesktopPathFound $true)  "not running + found -> start"
Assert-Equal "not_found" (Resolve-DockerAction -DaemonReady $false -DesktopRunning $false -DesktopPathFound $false) "not running + not found -> not_found"

# ---------------------------------------------------------------------------
# 6. docker info exit-code capture + stderr suppression
# ---------------------------------------------------------------------------
Write-Host "[6] docker info exit-code / stderr handling" -ForegroundColor Cyan
$fakeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-fakedocker-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $fakeDir | Out-Null
$fakeDocker = Join-Path $fakeDir "fake-docker.ps1"
Set-Content -LiteralPath $fakeDocker -Value @'
# Fake `docker` that emits an error (like a down daemon) and exits per env.
Write-Error "failed to connect to docker API at npipe:////./pipe/dockerDesktopLinuxEngine"
exit ([int]$env:FAKE_DOCKER_EXIT)
'@
try {
    $env:FAKE_DOCKER_EXIT = "1"
    $code = Invoke-DockerInfo -DockerCommand $fakeDocker
    Assert-Equal 1 $code "captures non-zero exit code without throwing"
    Assert-True (-not (Test-DockerDaemonReady -DockerCommand $fakeDocker)) "daemon reported NOT ready when docker info exits 1"

    $env:FAKE_DOCKER_EXIT = "0"
    Assert-Equal 0 (Invoke-DockerInfo -DockerCommand $fakeDocker) "captures exit code 0"
    Assert-True (Test-DockerDaemonReady -DockerCommand $fakeDocker) "daemon reported ready when docker info exits 0"

    Assert-Equal 255 (Invoke-DockerInfo -DockerCommand (Join-Path $fakeDir "does-not-exist")) "returns 255 when the CLI is missing"
} finally {
    Remove-Item Env:\FAKE_DOCKER_EXIT -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fakeDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("RESULT: {0} passed, {1} failed" -f $script:Pass, $script:Fail) -ForegroundColor Cyan
if ($script:Fail -gt 0) { exit 1 } else { exit 0 }
