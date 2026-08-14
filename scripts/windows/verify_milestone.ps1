<#
.SYNOPSIS
    Runs the acceptance gate for one V3 milestone.

.DESCRIPTION
    Blueprint V3 §Operating Model: verification is ONE command, never a manual
    multi-command sequence. This script runs the complete gate for the named
    milestone and exits non-zero on the first failure, so it is safe to use as
    a pre-merge check.

    Known milestones:
      M1  Instrumentation & Truthful Baseline

.PARAMETER Milestone
    Milestone id (e.g. M1). Case-insensitive.

.PARAMETER ProjectRoot
    Repository root. Defaults to the parent of scripts\windows.

.PARAMETER SkipFlaky
    Deselect tests known to be flaky in the CURRENT repository (pre-existing,
    not introduced by a milestone). Each exclusion is listed explicitly below
    so nothing is hidden.

.EXAMPLE
    .\scripts\windows\verify_milestone.ps1 M1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Milestone,

    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),

    [switch]$SkipFlaky
)

$ErrorActionPreference = "Stop"

# scripts\windows\verify_milestone.ps1 -> repo root is two levels up.
if (-not (Test-Path (Join-Path $ProjectRoot "backend"))) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
    $ProjectRoot = Split-Path -Parent $ProjectRoot
}

$Backend = Join-Path $ProjectRoot "backend"
if (-not (Test-Path $Backend)) {
    Write-Error "backend/ not found under '$ProjectRoot'. Pass -ProjectRoot explicitly."
    exit 1
}

# Prefer the project venv; fall back to PATH python.
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$script:Failures = @()

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)

    Write-Host ""
    Write-Host "── $Name " -NoNewline -ForegroundColor Cyan
    Write-Host ("─" * [Math]::Max(1, 60 - $Name.Length)) -ForegroundColor DarkGray
    try {
        & $Action
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
            throw "exit code $LASTEXITCODE"
        }
        Write-Host "   PASS" -ForegroundColor Green
    }
    catch {
        Write-Host "   FAIL: $_" -ForegroundColor Red
        $script:Failures += $Name
    }
}

Write-Host ""
Write-Host "AcademicOS — verifying $($Milestone.ToUpper())" -ForegroundColor White
Write-Host "root: $ProjectRoot"

Push-Location $Backend
try {
    # Pre-existing flaky test (NOT introduced by V3): a CPU-timing budget that
    # fails intermittently on shared/virtualised hardware. Verified failing on
    # pristine R1 with zero V3 code. Shared by every milestone gate.
    $deselect = @()
    if ($SkipFlaky) {
        $deselect = @(
            "--deselect",
            "app/tests/eval/test_l10_scale_budgets.py::test_l10_dlq_scale_ci_safe[10000]"
        )
    }

    switch ($Milestone.ToUpper()) {

        "M1" {

            Invoke-Step "Application imports" {
                & $Python -c "from app.main import app; assert len(app.routes) > 300"
            }

            Invoke-Step "Middleware ordering (telemetry outermost)" {
                & $Python -c @"
from app.main import app
names = [m.cls.__name__ for m in app.user_middleware]
assert names and names[0] == 'TelemetryMiddleware', names
"@
            }

            Invoke-Step "M1 suite (telemetry / readiness / pre-warm)" {
                & $Python -m pytest app/tests/integration/test_m1_telemetry_readiness.py -q -p no:cacheprovider
            }

            Invoke-Step "Architecture guardrails" {
                & $Python -m pytest app/tests/architecture -q -p no:cacheprovider
            }

            Invoke-Step "Full regression" {
                & $Python -m pytest -q -p no:cacheprovider @deselect
            }

            Invoke-Step "Baseline latency report" {
                & $Python scripts/baseline_latency.py --runs 20 --json ../docs/baseline/M1_baseline.json | Out-Null
            }
        }

        # V3 M2..M5 share one gate shape: milestone suite + architecture
        # guardrails + full regression (the known-flaky CPU-timing budget test
        # is deselected via -SkipFlaky, as in M1).
        "M2" {
            Invoke-Step "M2 suite (PDF repair / dead-route removal)" {
                & $Python -m pytest app/tests/unit/test_intake_extraction_engines.py -q -p no:cacheprovider
            }
            Invoke-Step "Architecture guardrails" {
                & $Python -m pytest app/tests/architecture -q -p no:cacheprovider
            }
            Invoke-Step "Full regression" {
                & $Python -m pytest -q -p no:cacheprovider @deselect
            }
        }

        "M3" {
            Invoke-Step "M3 suite (tenancy stamping)" {
                & $Python -m pytest app/tests/integration/test_m3_tenancy_stamping.py -q -p no:cacheprovider
            }
            Invoke-Step "Architecture guardrails" {
                & $Python -m pytest app/tests/architecture -q -p no:cacheprovider
            }
            Invoke-Step "Full regression" {
                & $Python -m pytest -q -p no:cacheprovider @deselect
            }
        }

        "M4" {
            Invoke-Step "M4 suite (Hindi search / tokenizer)" {
                & $Python -m pytest app/tests/unit/test_tokenizer.py app/tests/integration/test_m4_hindi_search.py -q -p no:cacheprovider
            }
            Invoke-Step "Architecture guardrails" {
                & $Python -m pytest app/tests/architecture -q -p no:cacheprovider
            }
            Invoke-Step "Full regression" {
                & $Python -m pytest -q -p no:cacheprovider @deselect
            }
        }

        "M5" {
            Invoke-Step "M5 suite (typed claims / rung-0)" {
                & $Python -m pytest app/tests/integration/test_m5_typed_claims.py -q -p no:cacheprovider
            }
            Invoke-Step "Architecture guardrails" {
                & $Python -m pytest app/tests/architecture -q -p no:cacheprovider
            }
            Invoke-Step "Full regression" {
                & $Python -m pytest -q -p no:cacheprovider @deselect
            }
        }

        default {
            Write-Error "Unknown milestone '$Milestone'. Known: M1 M2 M3 M4 M5"
            exit 2
        }
    }
}
finally {
    Pop-Location
}

Write-Host ""
if ($script:Failures.Count -gt 0) {
    Write-Host "GATE FAILED — $($script:Failures.Count) step(s):" -ForegroundColor Red
    $script:Failures | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "GATE PASSED — $($Milestone.ToUpper()) is verified." -ForegroundColor Green
Write-Host ""
exit 0
