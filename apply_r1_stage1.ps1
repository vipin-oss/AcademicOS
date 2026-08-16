# AcademicOS R1 Stage 1 — Bundle Application Script
# Applies the Stage 1 implementation changes to the R1 branch.
#
# Usage: .\apply_r1_stage1.ps1
#
# Base: e4313dc (R1 HEAD)
# Target: ceb175c (R1 + Stage 1)
#
# This script applies verified Stage 1 changes including:
# - Simplified upload (drag-and-drop, auto-derived fields)
# - 5-item customizable sidebar navigation
# - New Home page (attention center)
# - Records page (structured academic knowledge)
# - Unified AI surface (merged Assistant/Chat into AI)
# - Command Palette (Ctrl+K universal search)
# - Background AI enrichment after upload
# - Mobile responsive layout

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundleFile = Join-Path $scriptDir "AcademicOS_R1_Stage1_Bundle.bundle"
$expectedBase = "e4313dc"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AcademicOS R1 Stage 1 Bundle Application" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verify bundle exists
if (-not (Test-Path -LiteralPath $bundleFile)) {
    Write-Host "ERROR: Bundle file not found at $bundleFile" -ForegroundColor Red
    Write-Host "Expected: AcademicOS_R1_Stage1_Bundle.bundle in the repository root." -ForegroundColor Yellow
    exit 1
}

# Verify we're in a git repo
if (-not (Test-Path -LiteralPath (Join-Path $scriptDir ".git"))) {
    Write-Host "ERROR: Not a git repository. Run this script from the AcademicOS root." -ForegroundColor Red
    exit 1
}

Push-Location $scriptDir

# Verify current branch is R1
$currentBranch = git branch --show-current 2>&1
if ($currentBranch -ne "R1") {
    Write-Host "WARNING: Current branch is '$currentBranch', not 'R1'." -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Aborted." -ForegroundColor Yellow
        Pop-Location
        exit 0
    }
}

# Verify expected base commit
$currentHead = git rev-parse --short HEAD 2>&1
if ($currentHead -ne $expectedBase) {
    Write-Host "WARNING: Current HEAD is '$currentHead', expected '$expectedBase'." -ForegroundColor Yellow
    Write-Host "The bundle was created against R1 at $expectedBase." -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Aborted." -ForegroundColor Yellow
        Pop-Location
        exit 0
    }
}

# Check for uncommitted changes
$status = git status --porcelain 2>&1
if ($status) {
    Write-Host "WARNING: You have uncommitted changes:" -ForegroundColor Yellow
    Write-Host $status
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Aborted." -ForegroundColor Yellow
        Pop-Location
        exit 0
    }
}

# Verify bundle
Write-Host "Verifying bundle..." -ForegroundColor Cyan
$verify = git bundle verify $bundleFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Bundle verification failed." -ForegroundColor Red
    Write-Host $verify
    Pop-Location
    exit 1
}
Write-Host "Bundle verified OK." -ForegroundColor Green

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Would fetch and merge from bundle." -ForegroundColor Yellow
    Write-Host "Bundle contains these refs:" -ForegroundColor Yellow
    git bundle list-heads $bundleFile 2>&1
    Write-Host ""
    Write-Host "To apply, run without -DryRun." -ForegroundColor Yellow
    Pop-Location
    exit 0
}

# Create backup branch
$backupBranch = "backup-before-r1-stage1-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Write-Host "Creating backup branch: $backupBranch" -ForegroundColor Cyan
git branch $backupBranch 2>&1

# Fetch from bundle
Write-Host "Fetching changes from bundle..." -ForegroundColor Cyan
git fetch $bundleFile HEAD:refs/remotes/bundle/r1-stage1 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fetch from bundle." -ForegroundColor Red
    Pop-Location
    exit 1
}

# Merge
Write-Host "Merging R1 Stage 1 changes..." -ForegroundColor Cyan
git merge refs/remotes/bundle/r1-stage1 --no-edit 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Merge failed. Resolve conflicts manually or run:" -ForegroundColor Red
    Write-Host "  git merge --abort" -ForegroundColor Yellow
    Write-Host "  git checkout $backupBranch" -ForegroundColor Yellow
    Pop-Location
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "R1 Stage 1 applied successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Changes applied:" -ForegroundColor Cyan
Write-Host "  - Simplified upload (drag-and-drop, auto-derived fields)" -ForegroundColor White
Write-Host "  - 5-item customizable sidebar (Home, Docs, Records, AI, Settings)" -ForegroundColor White
Write-Host "  - New Home page (attention center)" -ForegroundColor White
Write-Host "  - Records page (structured academic knowledge)" -ForegroundColor White
Write-Host "  - Unified AI surface (/assistant and /chat redirect to /ai)" -ForegroundColor White
Write-Host "  - Command Palette (press Ctrl+K)" -ForegroundColor White
Write-Host "  - Background AI enrichment after upload" -ForegroundColor White
Write-Host "  - Mobile responsive layout" -ForegroundColor White
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host "  .\start_academicos.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Backup branch created: $backupBranch" -ForegroundColor Yellow
Write-Host "To rollback: git reset --hard $backupBranch" -ForegroundColor Yellow
Write-Host ""

Pop-Location
