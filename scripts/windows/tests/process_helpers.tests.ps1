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
# 7. cmd.exe quoting — the "%1 is not a valid Win32 application" / silent-fail fix
# ---------------------------------------------------------------------------
Write-Host "[7] cmd.exe /s /c quoting (spaced npm.cmd path)" -ForegroundColor Cyan

# With /s, cmd.exe strips the FIRST and LAST quote; a single pair around only
# the npm.cmd path gets BOTH stripped, so a spaced path breaks. The fix wraps
# the whole command in an OUTER pair so /s strips those and preserves the
# inner path quotes.
$expectedSpaced = '/d /s /c ""C:\Program Files\nodejs\npm.cmd" run dev -- --hostname 127.0.0.1 --port 3000"'
$specSpaced = Get-FrontendLaunchCommand -NpmCmd "C:\Program Files\nodejs\npm.cmd" -Port 3000 -Hostname "127.0.0.1"
Assert-Equal "cmd.exe" $specSpaced.FilePath "FilePath is cmd.exe"
Assert-Equal $expectedSpaced $specSpaced.ArgumentList "exact command line: outer quotes wrap the whole command (spaced path preserved)"
Assert-True ($specSpaced.ArgumentList.StartsWith("/d /s /c `"`"")) "outer quote pair opens right after /c"
Assert-True ($specSpaced.ArgumentList.EndsWith("`"")) "outer quote pair closes the command"

$expectedUnspaced = '/d /s /c ""C:\tools\npm.cmd" run dev -- --hostname 127.0.0.1 --port 3000"'
$specUnspaced = Get-FrontendLaunchCommand -NpmCmd "C:\tools\npm.cmd" -Port 3000 -Hostname "127.0.0.1"
Assert-Equal $expectedUnspaced $specUnspaced.ArgumentList "unspaced path also quoted (harmless, still correct)"

# ---------------------------------------------------------------------------
# 8-15. Real HTTP-server readiness tests (raw-socket probe + wait + launch)
# ---------------------------------------------------------------------------

# A stand-in "Next.js dev server": serves the __next marker (or plain HTML with
# --plain), and parses --port/--hostname from argv exactly like `next dev`.
$fakeServerSource = @'
#!/usr/bin/env python3
import sys, http.server, socketserver
port, host = 3000, "127.0.0.1"
args = sys.argv[1:]
plain = "--plain" in args
i = 0
while i < len(args):
    a = args[i]
    if a == "--port" and i + 1 < len(args):
        port = int(args[i + 1]); i += 2; continue
    if a == "--hostname" and i + 1 < len(args):
        host = args[i + 1]; i += 2; continue
    i += 1
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if plain:
            body = b'<!DOCTYPE html><html><head><title>Other</title></head><body><h1>unrelated service</h1></body></html>'
        else:
            body = b'<!DOCTYPE html><html><head><title>AcademicOS</title></head><body><div id="__next">AcademicOS dev</div></body></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass
socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer((host, port), Handler).serve_forever()
'@

$py = (Get-Command python3 -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Write-Host "  SKIP  python3 not available for the HTTP readiness tests" -ForegroundColor Yellow
} else {
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-http-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
    $srvScript = Join-Path $tmpDir "fake_next.py"
    Set-Content -LiteralPath $srvScript -Value $fakeServerSource -Encoding utf8
    & chmod +x $srvScript 2>$null

    $started = New-Object System.Collections.Generic.List[object]
    function Start-FakeHttp {
        param([int]$Port, [switch]$Plain)
        $args = @($srvScript, "--port", [string]$Port)
        if ($Plain) { $args += "--plain" }
        $proc = Start-Process -FilePath $py -ArgumentList $args -PassThru
        $script:started.Add($proc)
        return $proc
    }

    try {
        # Case 7: Test-FrontendHttp returns EXACTLY one [bool] (true path).
        Write-Host "[8] Test-FrontendHttp returns [bool] true (HTTP 200 + __next)" -ForegroundColor Cyan
        $null = Start-FakeHttp -Port 32001
        Start-Sleep -Milliseconds 600
        $r = Test-FrontendHttp -Hostname "127.0.0.1" -Port 32001 -Marker "__next"
        Assert-True ($r -is [bool]) "returns exactly [bool]"
        Assert-Equal $true $r "detects HTTP 200 + __next marker"

        # Case 6: HTTP 200 without the Next.js marker is rejected.
        Write-Host "[9] Test-FrontendHttp returns [bool] false (200 but no __next)" -ForegroundColor Cyan
        $null = Start-FakeHttp -Port 32002 -Plain
        Start-Sleep -Milliseconds 600
        $r2 = Test-FrontendHttp -Hostname "127.0.0.1" -Port 32002 -Marker "__next"
        Assert-True ($r2 -is [bool]) "returns exactly [bool] (reject case)"
        Assert-Equal $false $r2 "rejects an unrelated 200 without the Next.js marker"

        # Connection refused -> false (no crash).
        Write-Host "[10] Test-FrontendHttp returns [bool] false (connection refused)" -ForegroundColor Cyan
        $r3 = Test-FrontendHttp -Hostname "127.0.0.1" -Port 32099 -Marker "__next"
        Assert-True ($r3 -is [bool]) "returns exactly [bool] (refused case)"
        Assert-Equal $false $r3 "closed port -> false"

        # Case 8: Wait-FrontendReady returns EXACTLY one [int].
        Write-Host "[11] Wait-FrontendReady returns [int] and finds the port" -ForegroundColor Cyan
        $null = Start-FakeHttp -Port 32003
        Start-Sleep -Milliseconds 600
        $ready = Wait-FrontendReady -StartPort 32003 -PortSpan 0 -Marker "__next" -Attempts 10 -SleepSeconds 1 -Hostname "127.0.0.1"
        Assert-True ($ready -is [int]) "returns exactly [int]"
        Assert-Equal 32003 $ready "detects the ready port"

        # Case 3/4: skip an unrelated 200 on one port, find __next on the next.
        Write-Host "[12] Wait-FrontendReady skips unrelated 200, finds __next on the next port" -ForegroundColor Cyan
        $null = Start-FakeHttp -Port 32004 -Plain
        $null = Start-FakeHttp -Port 32005
        Start-Sleep -Milliseconds 600
        $ready2 = Wait-FrontendReady -StartPort 32004 -PortSpan 1 -Marker "__next" -Attempts 10 -SleepSeconds 1 -Hostname "127.0.0.1"
        Assert-True ($ready2 -is [int]) "returns exactly [int] (multi-port case)"
        Assert-Equal 32005 $ready2 "skips the unrelated 200 on 32004 and detects 32005"

        # Timeout -> exactly [int] 0.
        Write-Host "[13] Wait-FrontendReady returns [int] 0 on timeout" -ForegroundColor Cyan
        $ready3 = Wait-FrontendReady -StartPort 32006 -PortSpan 0 -Marker "__next" -Attempts 2 -SleepSeconds 1 -Hostname "127.0.0.1"
        Assert-True ($ready3 -is [int]) "returns exactly [int] (timeout case)"
        Assert-Equal 0 $ready3 "nothing comes up -> 0"

        # Case 1: already-running frontend is detected (reuse, no launch).
        Write-Host "[14] Already-running frontend is reused (no launch)" -ForegroundColor Cyan
        $null = Start-FakeHttp -Port 32007
        Start-Sleep -Milliseconds 600
        $reused = $false
        for ($pp = 32007; $pp -le 32007; $pp++) {
            if (Test-FrontendHttp -Hostname "127.0.0.1" -Port $pp -Marker "__next") { $reused = $true; break }
        }
        Assert-True $reused "already-running frontend detected immediately (reuse path)"

        # Case 2: end-to-end launch -> readiness -> PID tracking.
        Write-Host "[15] End-to-end: launch -> readiness -> PID tracking" -ForegroundColor Cyan
        $lo = Join-Path $tmpDir "out.log"
        $le = Join-Path $tmpDir "err.log"
        $port = 32008
        Push-Location $tmpDir
        try {
            $before = (Get-Location).Path
            $proc = $null
            try {
                $proc = Start-FrontendDevServer -NpmCmd $srvScript -FrontendDir $tmpDir -Port $port -Hostname "127.0.0.1" -LogOut $lo -LogErr $le
            } catch {
                $proc = $null
            }
            $after = (Get-Location).Path
            Assert-True ($null -ne $proc) "dev server process launched"
            Assert-Equal $before $after "caller location restored after launch"
            if ($proc) { $started.Add($proc) }
            $readyPort = Wait-FrontendReady -StartPort $port -PortSpan 1 -Marker "__next" -Attempts 15 -SleepSeconds 1 -Hostname "127.0.0.1"
            Assert-Equal $port $readyPort ("http://127.0.0.1:{0} becomes ready (HTTP 200 + __next)" -f $port)
            if ($proc -and $readyPort -gt 0) {
                Assert-True ($null -ne (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) "launched process is alive (trackable PID)"
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
                Assert-True (-not (Test-FrontendHttp -Hostname "127.0.0.1" -Port $port -Marker "__next")) "killing the tracked PID stops the server (ownership verified)"
            }
        } finally {
            Pop-Location
        }
    } finally {
        foreach ($p in $started) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# 16. Redirect-following: the real Windows failure mode (GET / -> 307 -> /login)
# ---------------------------------------------------------------------------
Write-Host "[16] Redirect-following (307 -> /login -> 200 + __next)" -ForegroundColor Cyan
$redirectServerSource = @'
#!/usr/bin/env python3
import sys, http.server, socketserver
# Mimics the Next.js auth middleware: GET / -> 307 -> /login ; /login -> 200 + __next.
port = 3000
args = sys.argv[1:]
if "--port" in args:
    port = int(args[args.index("--port") + 1])
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = b"http://localhost:%d/login" % port
            self.send_response(307)
            self.send_header("Location", "/login")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/login":
            body = b'<!DOCTYPE html><html><head><title>AcademicOS</title></head><body><div id="__next">login</div></body></html>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a):
        pass
socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer(("127.0.0.1", port), Handler).serve_forever()
'@
$py = (Get-Command python3 -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Write-Host "  SKIP  python3 not available" -ForegroundColor Yellow
} else {
    $tmpR = Join-Path ([System.IO.Path]::GetTempPath()) ("academicos-redir-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmpR | Out-Null
    $srv = Join-Path $tmpR "redir_next.py"
    Set-Content -LiteralPath $srv -Value $redirectServerSource -Encoding utf8
    & chmod +x $srv 2>$null
    $rport = 32011
    $proc = Start-Process -FilePath $py -ArgumentList @($srv, "--port", [string]$rport) -PassThru
    try {
        Start-Sleep -Milliseconds 700
        # A single GET / returns 307; the probe must FOLLOW it to /login.
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $ok = Test-FrontendHttp -Hostname "127.0.0.1" -Port $rport -Marker "__next"
        $sw.Stop()
        Assert-True ($ok -is [bool]) "returns exactly [bool]"
        Assert-Equal $true $ok "follows 307 -> /login and finds __next (the real-Windows bug)"
        Assert-True ($sw.Elapsed.TotalSeconds -lt 3) "detects quickly (no 120s stall)"

        # Wait-FrontendReady also detects the redirecting frontend.
        $ready = Wait-FrontendReady -StartPort $rport -PortSpan 0 -Marker "__next" -Attempts 3 -SleepSeconds 1 -Hostname "127.0.0.1"
        Assert-Equal $rport $ready "Wait-FrontendReady returns the redirecting port"
    } finally {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $tmpR -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# 17. netstat -ano PID parsing (frontend.pid ownership fallback)
# ---------------------------------------------------------------------------
Write-Host "[17] netstat -ano PID parsing (Get-NetstatListenerPid)" -ForegroundColor Cyan
$netstatLines = @(
    "  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1234",
    "  TCP    127.0.0.1:3000         0.0.0.0:0              LISTENING       29160",
    "  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       5512",
    "  TCP    [::1]:3000             [::]:0                 LISTENING       29160",
    "  TCP    127.0.0.1:30000        0.0.0.0:0              LISTENING       9999",
    "  TCP    127.0.0.1:5330         10.0.0.5:443           ESTABLISHED     7777"
)
Assert-Equal 29160 (Get-NetstatListenerPid -Port 3000 -NetstatLines $netstatLines) "finds the node listener PID on 3000"
Assert-Equal 5512 (Get-NetstatListenerPid -Port 8000 -NetstatLines $netstatLines) "finds the backend PID on 8000"
Assert-Equal 1234 (Get-NetstatListenerPid -Port 135 -NetstatLines $netstatLines) "finds PID on 135"
Assert-Equal 0 (Get-NetstatListenerPid -Port 9999 -NetstatLines $netstatLines) "no listener -> 0"
Assert-Equal 0 (Get-NetstatListenerPid -Port 300 -NetstatLines $netstatLines) "port 300 does not false-match 30000"
Assert-Equal 0 (Get-NetstatListenerPid -Port 5330 -NetstatLines $netstatLines) "ESTABLISHED is not a listener"

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("RESULT: {0} passed, {1} failed" -f $script:Pass, $script:Fail) -ForegroundColor Cyan
if ($script:Fail -gt 0) { exit 1 } else { exit 0 }
