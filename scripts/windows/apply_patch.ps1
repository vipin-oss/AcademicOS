# AcademicOS - Windows patch application automation (Sprint M10.1, final polish)
# ASCII-safe, PowerShell 5.1 + 7 compatible.
# Applies an incremental patch ZIP over the current project tree:
#   1. backs up every file the patch touches (timestamped),
#   2. extracts the patch preserving directory structure,
#   3. replaces changed files, deletes files listed in PATCH_MANIFEST.md,
#   4. reports Added / Modified / Deleted / Failed with exit codes.
#
# Usage:  .\apply_patch.ps1 AcademicOS_M11_Patch.zip
# Idempotent: re-applying the same patch reports 0 Added / 0 Modified.

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

function Write-Step { param([string]$Msg) Write-Host "[apply] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "FAIL  $Msg" -ForegroundColor Red }

# --- resolve the patch path ------------------------------------------------
if (-not (Test-Path -LiteralPath $PatchZip)) {
    Write-Fail ("Patch file not found: {0}" -f $PatchZip)
    exit 2
}
$PatchZip = (Resolve-Path $PatchZip).Path
if (-not $PatchZip.EndsWith(".zip", [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Fail "Expected a .zip patch file."
    exit 2
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "backend"))) {
    Write-Fail "Project root does not contain backend/ - run from the AcademicOS root."
    exit 2
}

# --- staging + backup ------------------------------------------------------
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$tempRoot = [System.IO.Path]::GetTempPath()
$work = Join-Path $tempRoot ("academicos_patch_" + $stamp)
$extract = Join-Path $work "extract"
$backupDir = Join-Path $work "backup"
[System.IO.Directory]::CreateDirectory($extract) | Out-Null
[System.IO.Directory]::CreateDirectory($backupDir) | Out-Null

Write-Step ("Backing up current files and extracting {0} ..." -f $PatchZip)
try {
    Expand-Archive -Path $PatchZip -DestinationPath $extract -Force
} catch {
    Write-Fail ("Failed to extract the patch: {0}" -f $_.Exception.Message)
    exit 3
}

# Locate the manifest (patch root or inside an AcademicOS/ folder).
$manifest = Join-Path $extract "PATCH_MANIFEST.md"
if (-not (Test-Path -LiteralPath $manifest)) {
    $candidate = Get-ChildItem -Path $extract -Recurse -Filter "PATCH_MANIFEST.md" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { $manifest = $candidate.FullName }
}
$hasManifest = Test-Path -LiteralPath $manifest

# Strip a single wrapper folder (AcademicOS/...) so wrapped and flat patch
# archives apply identically; mixed archives stay relative to the extract root.
$topEntries = @(Get-ChildItem -Path $extract -Force -ErrorAction SilentlyContinue)
if ($topEntries.Count -eq 1 -and $topEntries[0].PSIsContainer) {
    $relRoot = $topEntries[0].FullName
} else {
    $relRoot = $extract
}

# --- collect patch files (the manifest is installed too, so the project's
# manifest always reflects the applied state) -------------------------------
$patchFiles = @()
if ($hasManifest) {
    Get-ChildItem -Path $extract -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $patchFiles += $_.FullName.Substring($relRoot.Length).TrimStart("\", "/")
    }
} else {
    Write-Warn "PATCH_MANIFEST.md not found - assuming a flat patch (no deleted-file list)."
    Get-ChildItem -Path $extract -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $patchFiles += $_.FullName.Substring($relRoot.Length).TrimStart("\", "/")
    }
}

# --- manifest: parse Deleted Files -----------------------------------------
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

# --- detect conflicts -------------------------------------------------------
Write-Step "Checking for conflicts..."
foreach ($rel in $patchFiles) {
    $target = Join-Path $ProjectRoot $rel
    if (Test-Path -LiteralPath $target) {
        $patchHash = (Get-FileHash -LiteralPath (Join-Path $relRoot $rel) -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ($patchHash -ne $targetHash) {
            # Patch differs from the working copy: expected for a modified
            # file; flag only when the working copy is NEWER than the patch
            # (a stale patch applied out of order).
            if ((Get-Item -LiteralPath $target).LastWriteTime -gt (Get-Item -LiteralPath (Join-Path $relRoot $rel)).LastWriteTime) {
                $script:conflicts++
                Write-Warn ("Working copy of {0} is newer than the patch - applying anyway." -f $rel)
            }
        }
    }
}

# --- apply -----------------------------------------------------------------
Write-Step "Applying patch..."
foreach ($rel in $patchFiles) {
    $src = Join-Path $relRoot $rel
    $target = Join-Path $ProjectRoot $rel
    $targetDir = Split-Path $target -Parent
    try {
        if (-not (Test-Path -LiteralPath $targetDir)) { [System.IO.Directory]::CreateDirectory($targetDir) | Out-Null }
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) {
                continue  # identical already applied - idempotent re-apply
            }
            $backupName = (Split-Path $rel -Leaf) + "_" + $stamp + "_" + [IO.Path]::GetRandomFileName()
            Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir $backupName) -Force
            Copy-Item -LiteralPath $src -Destination $target -Force
            $script:modified++
        } else {
            Copy-Item -LiteralPath $src -Destination $target -Force
            $script:added++
        }
    } catch {
        $script:failed++
        Write-Fail ("Could not apply {0} : {1}" -f $rel, $_.Exception.Message)
    }
}

# --- delete obsolete files -------------------------------------------------
Write-Step "Removing obsolete files listed in the manifest..."
foreach ($rel in $deletedFiles) {
    $target = Join-Path $ProjectRoot $rel
    if (Test-Path -LiteralPath $target) {
        try {
            $backupName = (Split-Path $rel -Leaf) + "_" + $stamp + "_" + [IO.Path]::GetRandomFileName()
            Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir $backupName) -Force
            Remove-Item -LiteralPath $target -Force
            $script:deleted++
            Write-OK ("Deleted {0} (backed up)" -f $rel)
        } catch {
            $script:failed++
            Write-Fail ("Could not delete {0} : {1}" -f $rel, $_.Exception.Message)
        }
    }
}

# --- summary ---------------------------------------------------------------
Write-Step "Post-apply commands from the manifest:"
if ($hasManifest) {
    $mText = Get-Content -Raw -Path $manifest
    if ($mText -match "npm install") {
        Write-OK "Run: cd frontend && npm install"
    }
    if ($mText -match "alembic upgrade head") {
        Write-OK "Run: cd backend && alembic upgrade head"
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
Write-Host ("Backup of replaced files: {0}" -f $backupDir)

if ($script:failed -gt 0) { exit 1 }
exit 0
