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
# One raw-socket HTTP GET. Returns the full raw response text (headers + body),
# or $null on connect/read failure. Deterministic on PS 5.1 and PS 7: no
# Invoke-WebRequest (no proxy, no progress bar, no unreliable -TimeoutSec), an
# explicit connect timeout (BeginConnect + WaitOne) and read timeout, and
# `Connection: close` so a compliant server closes after responding (the read
# loop then terminates on EOF).
# ---------------------------------------------------------------------------
function _Send-HttpRequest {
    param(
        [string]$Hostname,
        [int]$Port,
        [string]$Path,
        [int]$TimeoutSec
    )
    $timeoutMs = [Math]::Max(250, [int]($TimeoutSec * 1000))
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Hostname, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($timeoutMs, $false)) { return $null }
        $client.EndConnect($async)
        $stream = $client.GetStream()
        $stream.ReadTimeout = $timeoutMs
        $req = "GET $Path HTTP/1.1`r`nHost: ${Hostname}:${Port}`r`nUser-Agent: AcademicOS-startup`r`nAccept: */*`r`nConnection: close`r`n`r`n"
        $bytes = [System.Text.Encoding]::ASCII.GetBytes($req)
        $stream.Write($bytes, 0, $bytes.Length)
        $buffer = New-Object "System.Byte[]" 8192
        $ms = New-Object System.IO.MemoryStream
        while ($true) {
            $n = $stream.Read($buffer, 0, $buffer.Length)
            if ($n -le 0) { break }
            $ms.Write($buffer, 0, $n)
            if ($ms.Length -ge 262144) { break }   # 256 KiB cap
        }
        return [System.Text.Encoding]::UTF8.GetString($ms.ToArray())
    } catch {
        return $null
    } finally {
        $client.Close()
    }
}

# Parse the HTTP status code from a raw response (e.g. "HTTP/1.1 307 ...").
# Returns the integer status, or -1 when the status line is malformed.
function _Get-HttpStatus([string]$Raw) {
    $end = $Raw.IndexOf("`r`n")
    if ($end -lt 0) { $end = $Raw.IndexOf("`n") }
    $line = if ($end -ge 0) { $Raw.Substring(0, $end) } else { $Raw }
    $parts = $line -split " "
    if ($parts.Count -lt 2) { return -1 }
    try { return [int]$parts[1] } catch { return -1 }
}

# Extract the Location header (case-insensitive) from a raw response.
# Returns "" when absent.
function _Get-HttpLocation([string]$Raw) {
    $headEnd = $Raw.IndexOf("`r`n`r`n")
    $head = if ($headEnd -ge 0) { $Raw.Substring(0, $headEnd) } else { $Raw }
    foreach ($line in ($head -split "`r`n")) {
        $colon = $line.IndexOf(":")
        if ($colon -gt 0) {
            $name = $line.Substring(0, $colon).Trim()
            if ($name -ieq "location") { return $line.Substring($colon + 1).Trim() }
        }
    }
    return ""
}

# Turn a Location header into a request path on the SAME host:port we are
# probing (e.g. "http://localhost:3000/login" -> "/login"; "/login" ->
# "/login"; "login" -> "/login"). Ignores the Location's host so a
# "localhost" vs "127.0.0.1" mismatch never breaks the probe.
function _Resolve-RedirectPath([string]$Location) {
    $loc = $Location.Trim()
    if ($loc -eq "") { return $null }
    if ($loc -match "^https?://") {
        $withoutScheme = $loc -replace "^https?://", ""
        $slash = $withoutScheme.IndexOf("/")
        if ($slash -lt 0) { return "/" }
        return $withoutScheme.Substring($slash)
    }
    if ($loc.StartsWith("/")) { return $loc }
    return "/" + $loc
}

# ---------------------------------------------------------------------------
# True when http://<host>:<port>/ serves the AcademicOS frontend: the request
# chain must end in an HTTP 2xx whose body contains the Next.js marker
# (Next.js always renders inside <div id="__next">).
#
# FOLLOWS REDIRECTS: the Next.js auth middleware answers "GET /" with
# "307 -> /login"; a single GET / (or accepting only 200) therefore returns a
# FALSE negative even though the frontend is healthy. This follows the 3xx
# Location (up to MaxRedirects hops) and checks the FINAL 2xx response body —
# the same end-to-end result the user's Invoke-WebRequest sees, but on a
# deterministic raw socket with no proxy/progress-bar/timeout surprises.
#
# Guarantees:
#   - returns EXACTLY ONE [bool] (never null / array / extra output);
#   - never throws (every failure path returns [bool]$false);
#   - only accepts a final 2xx whose body contains the marker, so an
#     unrelated service that returns 200 is NOT mistaken for the frontend.
# ---------------------------------------------------------------------------
function Test-FrontendHttp {
    param(
        [string]$Hostname = "127.0.0.1",
        [int]$Port = 3000,
        [string]$Marker = "__next",
        [int]$TimeoutSec = 2,
        [int]$MaxRedirects = 3
    )
    if ([string]::IsNullOrWhiteSpace($Hostname) -or $Port -le 0) { return [bool]$false }
    $path = "/"
    for ($hop = 0; $hop -le $MaxRedirects; $hop++) {
        $raw = _Send-HttpRequest -Hostname $Hostname -Port $Port -Path $path -TimeoutSec $TimeoutSec
        if ($null -eq $raw) { return [bool]$false }
        $status = _Get-HttpStatus $raw
        if ($status -lt 0) { return [bool]$false }
        if ($status -ge 300 -and $status -lt 400) {
            $loc = _Get-HttpLocation $raw
            if ([string]::IsNullOrWhiteSpace($loc)) { return [bool]$false }
            $path = _Resolve-RedirectPath $loc
            if ($null -eq $path) { return [bool]$false }
            continue
        }
        if ($status -lt 200 -or $status -ge 300) { return [bool]$false }
        # Final 2xx: require the Next.js marker in the response.
        if ($raw.IndexOf($Marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return [bool]$true }
        return [bool]$false
    }
    return [bool]$false   # too many redirects
}

# ---------------------------------------------------------------------------
# Poll a port range until the frontend dev server answers with the marker.
# Returns EXACTLY ONE [int] (the ready port) or [int]0 on timeout. Next.js dev
# may auto-increment the port if the requested one is taken, hence the span.
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
                return [int]$p
            }
        }
        Start-Sleep -Seconds $SleepSeconds
    }
    return [int]0
}

# ---------------------------------------------------------------------------
# Parse `netstat -ano` output for the PID of the process LISTENING on $Port.
# Returns the PID, or 0 when the port is not listening. This is the reliable
# fallback for PID discovery when Get-NetTCPConnection comes back empty in a
# non-elevated session (the real-Windows frontend.pid failure). Pure function
# (takes the netstat lines as input) so it is unit-testable.
#
#   TCP    127.0.0.1:3000    0.0.0.0:0    LISTENING    29160
#   TCP    [::1]:3000        [::]:0       LISTENING    29160
# ---------------------------------------------------------------------------
function Get-NetstatListenerPid {
    param(
        [int]$Port,
        [string[]]$NetstatLines
    )
    foreach ($line in $NetstatLines) {
        if ($line -match "^\s*TCP\s+(\S+)\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            if ($Matches[1].EndsWith(":$Port")) {
                return [int]$Matches[2]
            }
        }
    }
    return [int]0
}
