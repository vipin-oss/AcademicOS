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
# True when http://<host>:<port>/ answers HTTP 200 AND the body contains the
# marker (Next.js always renders its app inside <div id="__next">, so
# "__next" is a reliable "the dev server is actually serving" signal).
#
# WHY RAW SOCKETS (not Invoke-WebRequest):
#   Windows PowerShell 5.1's Invoke-WebRequest renders a progress bar and goes
#   through the system proxy, and its -TimeoutSec does NOT reliably bound a
#   request whose server has accepted the connection but is not yet responding
#   (Next.js dev blocks the first GET / for 5-30s while it compiles). A raw
#   TcpClient probe with an explicit connect timeout (BeginConnect + WaitOne)
#   and read timeout (NetworkStream.ReadTimeout) is deterministic, fast, and
#   behaves identically on Windows PowerShell 5.1 and PowerShell 7.
#
# Guarantees:
#   - returns EXACTLY ONE [bool] (never null / array / extra output);
#   - never throws (every failure path returns [bool]$false);
#   - only accepts a real HTTP 200 whose body contains the marker, so an
#     unrelated service that returns 200 is NOT mistaken for the frontend.
# ---------------------------------------------------------------------------
function Test-FrontendHttp {
    param(
        [string]$Hostname = "127.0.0.1",
        [int]$Port = 3000,
        [string]$Marker = "__next",
        [int]$TimeoutSec = 2
    )
    if ([string]::IsNullOrWhiteSpace($Hostname) -or $Port -le 0) { return [bool]$false }
    $timeoutMs = [Math]::Max(250, [int]($TimeoutSec * 1000))
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Hostname, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($timeoutMs, $false)) { return [bool]$false }
        $client.EndConnect($async)
        $stream = $client.GetStream()
        $stream.ReadTimeout = $timeoutMs
        # HTTP/1.1 with Connection: close so the server closes after the
        # response (the read loop below then terminates on EOF). No
        # Accept-Encoding is sent, so the server must NOT gzip the body.
        $req = "GET / HTTP/1.1`r`nHost: ${Hostname}:${Port}`r`nUser-Agent: AcademicOS-startup`r`nAccept: */*`r`nConnection: close`r`n`r`n"
        $reqBytes = [System.Text.Encoding]::ASCII.GetBytes($req)
        $stream.Write($reqBytes, 0, $reqBytes.Length)
        $buffer = New-Object -TypeName 'System.Byte[]' -ArgumentList 8192
        $ms = New-Object System.IO.MemoryStream
        while ($true) {
            $n = $stream.Read($buffer, 0, $buffer.Length)
            if ($n -le 0) { break }
            $ms.Write($buffer, 0, $n)
            if ($ms.Length -ge 131072) { break }   # 128 KiB cap
        }
        $text = [System.Text.Encoding]::UTF8.GetString($ms.ToArray())
    } catch {
        return [bool]$false
    } finally {
        $client.Close()
    }
    # Status line must be an HTTP 200 (rejects 404/500/redirects).
    if (-not ($text.StartsWith("HTTP/1.0 200") -or $text.StartsWith("HTTP/1.1 200"))) { return [bool]$false }
    # Body must contain the Next.js marker (rejects unrelated HTTP services).
    if ($text.IndexOf($Marker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return [bool]$false }
    return [bool]$true
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
