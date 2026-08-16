# AcademicOS - process-launch helpers (Windows; dot-sourceable + unit-tested)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
#
# Windows-specific process-launch utilities for the one-command startup. They
# are dot-sourced by start_academicos.ps1 AND by the test harness
# (scripts/windows/tests/process_helpers.tests.ps1), so keep them free of
# script-level state ($ProjectRoot, $runDir, etc.).
#
# Root-cause note (frontend): on Windows `npm` is `npm.cmd` (a batch file),
# NOT a native executable. `Start-Process -FilePath "npm"` therefore fails
# with "%1 is not a valid Win32 application" because Start-Process cannot
# execute a .cmd/.bat directly. The fix is to resolve the real `npm.cmd` path
# and launch it via `cmd.exe /d /s /c`.

# ---------------------------------------------------------------------------
# Resolve the npm command to a concrete executable path.
# On Windows this is the full path to npm.cmd; elsewhere it is the npm binary.
# Returns $null when npm is not installed.
# ---------------------------------------------------------------------------
function Resolve-NpmCmd {
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

# ---------------------------------------------------------------------------
# Build a Start-Process launch spec for the frontend dev server (pure, no
# side effects). Returns a hashtable @{ FilePath; ArgumentList } or $null when
# no npm command was supplied.
#
# - Windows (.cmd/.bat): FilePath = "cmd.exe", ArgumentList = a command line of
#   the form  `/d /s /c ""<npm.cmd>" run dev -- --hostname <h> --port <p>".
#
#   WHY THE OUTER QUOTES: with `cmd.exe /s /c`, the /s switch strips the FIRST
#   and LAST quote on the line. A single pair around only the npm.cmd path
#   (e.g.  /d /s /c "C:\Program Files\nodejs\npm.cmd" run dev ...)  gets BOTH
#   quotes stripped by /s, so a path containing a space ("Program Files") then
#   breaks and cmd.exe silently fails to run npm at all. Wrapping the WHOLE
#   command in an outer quote pair makes /s strip the OUTER pair and PRESERVE
#   the inner pair around the spaced path — exactly how a user's manual
#   `npm run dev` resolves it.
# - Non-Windows: FilePath = the npm binary, ArgumentList = `run dev -- ...`.
# ---------------------------------------------------------------------------
function Get-FrontendLaunchCommand {
    param(
        [string]$NpmCmd,
        [int]$Port = 3000,
        [string]$Hostname = "127.0.0.1"
    )
    if (-not $NpmCmd) { return $null }
    $runArgs = "run dev -- --hostname $Hostname --port $Port"
    if ($NpmCmd -match '\.(cmd|bat)$') {
        return @{
            FilePath     = "cmd.exe"
            ArgumentList = '/d /s /c ""{0}" {1}"' -f $NpmCmd, $runArgs
        }
    }
    return @{
        FilePath     = $NpmCmd
        ArgumentList = $runArgs
    }
}

# ---------------------------------------------------------------------------
# Pure decision: should the startup reuse an already-serving frontend or start
# a new one? This is the "no duplicate frontend process" guarantee, expressed
# as data (mirrors Resolve-DockerAction).
# ---------------------------------------------------------------------------
function Resolve-FrontendAction {
    param([bool]$HealthyFrontendDetected)
    if ($HealthyFrontendDetected) { return "reuse" }
    return "start"
}

# ---------------------------------------------------------------------------
# Launch the frontend dev server and GUARANTEE the caller's working directory
# is restored (Push-Location in a try/finally) even if Start-Process throws.
# Returns the launched Process object (PassThru), or $null when there is
# nothing to launch.
# ---------------------------------------------------------------------------
function Start-FrontendDevServer {
    param(
        [string]$NpmCmd,
        [string]$FrontendDir,
        [int]$Port = 3000,
        [string]$Hostname = "127.0.0.1",
        [string]$LogOut = "",
        [string]$LogErr = ""
    )
    $spec = Get-FrontendLaunchCommand -NpmCmd $NpmCmd -Port $Port -Hostname $Hostname
    if (-not $spec) { return $null }

    Push-Location $FrontendDir
    try {
        $launchArgs = @{
            FilePath         = $spec.FilePath
            ArgumentList     = $spec.ArgumentList
            WorkingDirectory = $FrontendDir
            PassThru         = $true
        }
        # -WindowStyle is Windows-only (not valid on PowerShell on Linux/macOS);
        # keep the process hidden on Windows, skip the flag elsewhere.
        $onWindows = ($PSVersionTable.PSEdition -eq "Desktop") -or [bool]$IsWindows
        if ($onWindows) { $launchArgs.WindowStyle = "Hidden" }
        if ($LogOut) { $launchArgs.RedirectStandardOutput = $LogOut }
        if ($LogErr) { $launchArgs.RedirectStandardError = $LogErr }
        return (Start-Process @launchArgs)
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# True when http://<host>:<port>/ answers HTTP 200 and the body contains the
# marker (Next.js always renders its app inside <div id="__next">, so
# "__next" is a reliable "the dev server is actually serving" signal).
# Never throws; a timeout / connection refusal / non-200 returns $false.
# ---------------------------------------------------------------------------
function Test-FrontendHttp {
    param(
        [string]$Hostname = "127.0.0.1",
        [int]$Port = 3000,
        [string]$Marker = "__next",
        [int]$TimeoutSec = 2
    )
    try {
        $r = Invoke-WebRequest -Uri ("http://{0}:{1}" -f $Hostname, $Port) -UseBasicParsing -TimeoutSec $TimeoutSec
        if ($r.StatusCode -eq 200 -and ($r.Content -match $Marker)) { return $true }
    } catch {
        # connection refused / timeout / non-200 -> not ready yet
    }
    return $false
}

# ---------------------------------------------------------------------------
# Poll a port range until the frontend dev server answers with the marker.
# Returns the ready port, or 0 on timeout. Next.js dev may auto-increment the
# port if the requested one is taken, hence the span.
# ---------------------------------------------------------------------------
function Wait-FrontendReady {
    param(
        [int]$StartPort = 3000,
        [int]$PortSpan = 10,
        [string]$Marker = "__next",
        [int]$Attempts = 60,
        [int]$SleepSeconds = 2,
        [string]$Hostname = "127.0.0.1"
    )
    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        for ($p = $StartPort; $p -le ($StartPort + $PortSpan); $p++) {
            if (Test-FrontendHttp -Hostname $Hostname -Port $p -Marker $Marker) {
                return $p
            }
        }
        Start-Sleep -Seconds $SleepSeconds
    }
    return 0
}
