# AcademicOS - Docker Desktop helpers (Windows; dot-sourceable + unit-tested)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Pure, side-effect-light functions for the one-command startup's Docker step.
# They never throw and never kill or interfere with unrelated processes. They
# are dot-sourced by start_academicos.ps1 AND by the test harness
# (scripts/windows/tests/docker_helpers.tests.ps1), so keep them free of any
# dependency on script-level state ($ProjectRoot, $runDir, etc.).
#
# Root-cause note: on Windows the `docker` CLI ships with Docker Desktop, but
# the Linux engine (daemon) is a SEPARATE thing that only runs while Docker
# Desktop is up. When the engine is down, `docker info` prints
#   failed to connect to docker API at npipe:////./pipe/dockerDesktopLinuxEngine
# and exits non-zero. The startup must therefore (a) discover and launch Docker
# Desktop, and (b) POLL for the daemon rather than treating the first failure
# as fatal (Docker Desktop can take 30-120s to boot the engine).

# ---------------------------------------------------------------------------
# Safe docker-info probe.
#
# Runs `docker info`, suppresses native stderr noise (PS 7.3+ would otherwise
# convert stderr into a NativeCommandError that terminates the script under
# $ErrorActionPreference = "Stop"), and returns the raw exit code
# (0 = daemon ready; 255 = CLI not found; other = daemon down / error).
# ---------------------------------------------------------------------------
function Invoke-DockerInfo {
    param([string]$DockerCommand = "docker")
    if (-not (Get-Command $DockerCommand -ErrorAction SilentlyContinue)) { return 255 }
    $prevNative = $PSNativeCommandUseErrorActionPreference
    $prevEAP = $ErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $DockerCommand info 2>&1 | Out-Null
        return $LASTEXITCODE
    } finally {
        $PSNativeCommandUseErrorActionPreference = $prevNative
        $ErrorActionPreference = $prevEAP
    }
}

# True when the Docker CLI is present AND the daemon answers `docker info`.
function Test-DockerDaemonReady {
    param([string]$DockerCommand = "docker")
    return ((Invoke-DockerInfo -DockerCommand $DockerCommand) -eq 0)
}

# True when a "Docker Desktop" process is running.
function Test-DockerDesktopRunning {
    param([string]$ProcessName = "Docker Desktop")
    return ($null -ne (Get-Process -Name $ProcessName -ErrorAction SilentlyContinue | Select-Object -First 1))
}

# ---------------------------------------------------------------------------
# Discover the Docker Desktop executable WITHOUT hardcoding a single path.
# Discovery order (most authoritative first):
#   1. the running "Docker Desktop" process's own executable path;
#   2. the registry install location (HKLM then HKCU: ExePath / InstallDir);
#   3. well-known install folders (Program Files, Program Files (x86), LocalAppData);
#   4. "Docker Desktop.exe" on PATH.
# Returns the path, or $null when Docker Desktop is not installed.
# ---------------------------------------------------------------------------
function Get-DockerDesktopPath {
    # 1. Running process (its Path is authoritative and covers any install dir).
    $proc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc -and $proc.Path) { return $proc.Path }

    # 2. Registry (Docker Desktop records its install dir here).
    $regKeys = @(
        "HKLM:\SOFTWARE\Docker Inc.\Docker Desktop",
        "HKCU:\SOFTWARE\Docker Inc.\Docker Desktop"
    )
    foreach ($key in $regKeys) {
        if (Test-Path -LiteralPath $key) {
            $props = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
            foreach ($valueName in @("ExePath", "InstallDir", "AppPath")) {
                $raw = $props.PSObject.Properties[$valueName]
                if ($raw -and $raw.Value) {
                    $candidate = [string]$raw.Value
                    if ($candidate -notmatch "Docker Desktop\.exe$") {
                        $candidate = Join-Path $candidate "Docker Desktop.exe"
                    }
                    if (Test-Path -LiteralPath $candidate) { return $candidate }
                }
            }
        }
    }

    # 3. Well-known install folders.
    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe")
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }

    # 4. On PATH.
    $cmd = Get-Command "Docker Desktop.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    return $null
}

# ---------------------------------------------------------------------------
# Pure decision: what should the startup DO about Docker, given three facts?
#   "reuse"     - daemon already up; do nothing.
#   "wait"      - daemon down but Docker Desktop already running; just poll
#                 (NEVER launch a second copy).
#   "start"     - daemon down, Docker Desktop not running, executable found.
#   "not_found" - daemon down, not running, executable not found.
# This function is the "no duplicate launch" guarantee, expressed as data.
# ---------------------------------------------------------------------------
function Resolve-DockerAction {
    param(
        [bool]$DaemonReady,
        [bool]$DesktopRunning,
        [bool]$DesktopPathFound
    )
    if ($DaemonReady) { return "reuse" }
    if ($DesktopRunning) { return "wait" }
    if ($DesktopPathFound) { return "start" }
    return "not_found"
}

# ---------------------------------------------------------------------------
# Poll until the probe returns $true or the timeout elapses. Returns $true on
# readiness, $false on timeout. `-OnTick` is called after each failed poll
# with the elapsed seconds (for progress output). Docker Desktop can take
# 30-120s to boot its engine, so the default timeout is generous.
# ---------------------------------------------------------------------------
function Wait-DockerDaemon {
    param(
        [scriptblock]$Probe = { Test-DockerDaemonReady },
        [int]$TimeoutSeconds = 180,
        [int]$PollSeconds = 5,
        [scriptblock]$OnTick = $null
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (& $Probe) { return $true }
        if ($OnTick) { & $OnTick ([int]$sw.Elapsed.TotalSeconds) }
        Start-Sleep -Seconds $PollSeconds
    }
    # One final check (it may have come up just as the timeout hit).
    if (& $Probe) { return $true }
    return $false
}
