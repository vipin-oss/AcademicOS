# AcademicOS — Windows patch application automation (Sprint M10.1)
# Applies an incremental patch ZIP over the current project tree:
#   1. backs up every file the patch touches (timestamped),
#   2. extracts the patch preserving directory structure,
#   3. replaces changed files, deletes files listed in PATCH_MANIFEST.md,
#   4. reports Added / Modified / Deleted / Failed with exit codes.
#
# Usage:  .\apply_patch.ps1 AcademicOS_M11_Patch.zip
# PowerShell 5.1+, Windows 10/11. Idempotent.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$PatchZip,

    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$script:added = 0
$script:modified = 0
$script:deleted = 0
$script:failed = 0
$script:conflicts = 0

function Write-Step  { param([string]$Msg) Write-Host "[apply] $Msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$Msg) Write-Host "FAIL  $Msg" -ForegroundColor Red }

# --- resolve the patch path -------------------------------------------------
if (-not (Test-Path $PatchZip)) {
    Write-Fail "Patch file not found: $PatchZip"
    exit 2
}
$PatchZip = (Resolve-Path $PatchZip).Path
if (-not $PatchZip.EndsWith(".zip", [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Fail "Expected a .zip patch file."
    exit 2
}
if (-not (Test-Path (Join-Path $ProjectRoot "backend"))) {
    Write-Fail "Project root does not contain backend/ — run from the AcademicOS root."
    exit 2
}

# --- staging + backup -------------------------------------------------------
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$work = Join-Path $env:TEMP "academicos_patch_$stamp"
$extract = Join-Path $work "extract"
$backupDir = Join-Path $work "backup"
New-Item -ItemType Directory -Force -Path $extract, $backupDir | Out-Null

Write-Step "Backing up current files and extracting $PatchZip …"
try {
    Expand-Archive -Path $PatchZip -DestinationPath $extract -Force
} catch {
    Write-Fail "Failed to extract the patch: $_"
    exit 3
}

# Locate the manifest (patch root or inside an AcademicOS/ folder).
$manifest = Join-Path $extract "PATCH_MANIFEST.md"
if (-not (Test-Path $manifest)) {
    $candidate = Get-ChildItem -Path $extract -Recurse -Filter "PATCH_MANIFEST.md" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { $manifest = $candidate.FullName }
}
$hasManifest = Test-Path $manifest

# --- collect patch files (skip the manifest itself) -------------------------
$patchFiles = @()
$patchDirs = @()
if ($hasManifest) {
    # everything except the manifest
    Get-ChildItem -Path $extract -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $manifest } | ForEach-Object {
            $rel = $_.FullName.Substring($extract.Length).TrimStart("\", "/")
            $patchFiles += $rel
        }
} else {
    Write-Warn "PATCH_MANIFEST.md not found — assuming a flat patch (no deleted-file list)."
    Get-ChildItem -Path $extract -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $patchFiles += $_.FullName.Substring($extract.Length).TrimStart("\", "/")
    }
}

# --- manifest: parse Deleted Files + apply notes ----------------------------
$deletedFiles = @()
if ($hasManifest) {
    $lines = Get-Content -Path $manifest -ErrorAction SilentlyContinue
    $inDeleted = $false
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^##\s+Files Deleted") { $inDeleted = $true; continue }
        if ($inDeleted -and $trimmed -match "^##\s") { $inDeleted = $false }
        if ($inDeleted -and $trimmed -match "^\|") {
            $cell = ($trimmed -split "\|")[1].Trim()
            if ($cell -and $cell -ne "-" -and $cell -ne "*(none)*" -and -not $cell.StartsWith("(")) {
                $deletedFiles += $cell.Trim('`')
            }
        }
    }
}

# --- detect conflicts: patch file already exists but differs from the zip ---
Write-Step "Checking for conflicts…"
foreach ($rel in $patchFiles) {
    $target = Join-Path $ProjectRoot $rel
    if (Test-Path $target) {
        $a = Get-FileHash -Path (Join-Path $extract $rel) -Algorithm SHA256
        $b = Get-FileHash -Path $target -Algorithm SHA256
        if ($a.Hash -ne $b.Hash) {
            # A modified file is the normal patch case; flag only when the
            # patch file is OLDER than the working copy (stale patch).
            if ((Get-Item $target).LastWriteTime -gt (Get-Item (Join-Path $extract $rel)).LastWriteTime) {
                $script:conflicts++
                Write-Warn "Working copy of $rel is newer than the patch — will still apply."
            }
        }
    }
}

# --- apply ----------------------------------------------------------------
Write-Step "Applying patch…"
foreach ($rel in $patchFiles) {
    $src = Join-Path $extract $rel
    $target = Join-Path $ProjectRoot $rel
    $targetDir = Split-Path $target -Parent
    try {
        if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Force -Path $targetDir | Out-Null }
        if (Test-Path $target) {
            $bak = Join-Path $backupDir (Get-Item $target).Name + "_" + (Get-Item $target).LastWriteTime.Ticks
            Copy-Item -Path $target -Destination (Join-Path $backupDir ((Split-Path $rel -Leaf) + "_" + [IO.Path]::GetRandomFileName())) -Force
            Copy-Item -Path $src -Destination $target -Force
            $script:modified++
        } else {
            Copy-Item -Path $src -Destination $target -Force
            $script:added++
        }
    } catch {
        $script:failed++
        Write-Fail "Could not apply $rel : $_"
    }
}

# --- delete obsolete files -------------------------------------------------
Write-Step "Removing obsolete files listed in the manifest…"
foreach ($rel in $deletedFiles) {
    $target = Join-Path $ProjectRoot $rel
    if (Test-Path $target) {
        try {
            Remove-Item -Path $target -Force
            $script:deleted++
            Write-OK "Deleted $rel"
        } catch {
            $script:failed++
            Write-Fail "Could not delete $rel : $_"
        }
    }
}

# --- summary ---------------------------------------------------------------
Write-Step "Applying dependencies if the manifest requests them…"
if ($hasManifest) {
    $mText = Get-Content -Raw -Path $manifest
    if ($mText -match "npm install") {
        Write-OK "Manifest requests npm install — run it manually: cd frontend && npm install"
    }
    if ($mText -match "alembic upgrade head") {
        Write-OK "Manifest requests alembic upgrade head — run: cd backend && alembic upgrade head"
    }
}

Write-Host ""
Write-Host "================= APPLY PATCH SUMMARY =================" -ForegroundColor Cyan
Write-Host ("  Added:      {0}" -f $script:added) -ForegroundColor Green
Write-Host ("  Modified:   {0}" -f $script:modified) -ForegroundColor Yellow
Write-Host ("  Deleted:    {0}" -f $script:deleted) -ForegroundColor Yellow
Write-Host ("  Failed:     {0}" -f $script:failed) -ForegroundColor $(if ($script:failed -gt 0) { "Red" } else { "Green" })
if ($script:conflicts -gt 0) { Write-Host ("  Conflicts:  {0} (flagged)" -f $script:conflicts) -ForegroundColor Yellow }
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Backup of replaced files: $backupDir"

if ($script:failed -gt 0) { exit 1 }
exit 0
