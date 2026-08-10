<#
.SYNOPSIS
  AcademicOS - repair the malformed local-Ollama base_url in backend/.env.

.DESCRIPTION
  Root cause: a Markdown-formatted link was accidentally pasted into the
  AI_PROVIDERS_JSON "base_url" field of backend/.env, e.g.
      [[http://localhost:11434/v1](http://localhost:11434/v1)](http://localhost:11434/v1](http://localhost:11434/v1))
  AcademicOS parses that string verbatim as the provider base_url; at request
  time httpx rejects it ("Request URL is missing an 'http://' or 'https://'
  protocol") and AI chat returns an unavailable/error response.

  The repository code is correct - only the local .env is wrong. This script
  normalizes ONLY the base_url back to the literal
      http://localhost:11434/v1
  It is safe, idempotent, backs up the original .env, and never asks you to
  type or paste a URL or edit JSON by hand.

  Compatibility: pure ASCII, Windows PowerShell 5.1 and PowerShell 7+.
  Does NOT use ConvertTo-Json -Compress (absent before PowerShell 6).

.PARAMETER RepoRoot
  Path to the AcademicOS repo root (defaults to the current directory).
  Run it from E:\AcademicOS so the default is correct.

.EXAMPLE
  cd E:\AcademicOS
  powershell -ExecutionPolicy Bypass -File .\academicOS-env-fix\APPLY_FIX.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$IntendedUrl = 'http://localhost:11434/v1'
$EnvFile     = Join-Path $RepoRoot 'backend\.env'
$ExampleFile = Join-Path $RepoRoot 'backend\.env.example'

function Test-GoodBaseUrl([string]$Url) {
    # A "good" base_url starts with http(s):// and contains no brackets/parens.
    return ($Url -match '^https?://[^\[\]\(\)]+$')
}

function Test-LocalOllama([string]$Url) {
    return ($Url -match '(localhost|127\.0\.0\.1|11434)')
}

function ConvertTo-CompactJsonString([string]$Value) {
    # Escape a string for a JSON string value (backslash first).
    $s = $Value
    if ($null -eq $s) { return '' }
    $s = $s -replace '\\', '\\'
    $s = $s -replace '"', '\"'
    $s = $s -replace "`r", '\r'
    $s = $s -replace "`n", '\n'
    $s = $s -replace "`t", '\t'
    return $s
}

function Convert-ObjectToCompactJson([object]$Obj) {
    # Serialize ALL properties (preserves extra fields like embedding_model),
    # compact, one line. Works on Windows PowerShell 5.1 (no -Compress needed).
    $parts = @()
    foreach ($prop in $Obj.PSObject.Properties) {
        $name = $prop.Name
        $val  = $prop.Value
        if ($null -eq $val) {
            $parts += '"' + $name + '":null'
        }
        elseif ($val -is [bool]) {
            $parts += '"' + $name + '":' + $(if ($val) { 'true' } else { 'false' })
        }
        elseif ($val -is [int] -or $val -is [long] -or $val -is [double] -or $val -is [decimal]) {
            $parts += '"' + $name + '":' + $val.ToString([System.Globalization.CultureInfo]::InvariantCulture)
        }
        else {
            $parts += '"' + $name + '":"' + (ConvertTo-CompactJsonString([string]$val)) + '"'
        }
    }
    return '{' + ($parts -join ',') + '}'
}

function Convert-ProvidersToCompactJsonArray([object[]]$Providers) {
    $items = @()
    foreach ($p in $Providers) { $items += (Convert-ObjectToCompactJson $p) }
    return '[' + ($items -join ',') + ']'
}

Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ' AcademicOS - local Ollama base_url repair' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host "Repo root : $RepoRoot"
Write-Host "Env file  : $EnvFile"
Write-Host "Target URL: $IntendedUrl"

# --- Step 1: ensure backend/.env exists ---------------------------------
if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (Test-Path -LiteralPath $ExampleFile) {
        Write-Host 'backend/.env not found - copying from backend/.env.example' -ForegroundColor Yellow
        Copy-Item -LiteralPath $ExampleFile -Destination $EnvFile -Force
    }
    else {
        throw 'backend/.env not found and no backend/.env.example to copy. Run this script from the repo root (e.g. E:\AcademicOS).'
    }
}

# --- Step 2: back up the current .env -----------------------------------
$stamp  = (Get-Date -Format 'yyyyMMdd-HHmmss')
$Backup = "$EnvFile.bak-$stamp"
Copy-Item -LiteralPath $EnvFile -Destination $Backup -Force
Write-Host "Backed up to: $Backup" -ForegroundColor DarkGray

# --- Step 3: read .env, fix only the relevant lines ---------------------
# @() forces an array so a single-line file indexes as lines, not characters.
$lines           = @(Get-Content -LiteralPath $EnvFile)
$fixedAny        = $false
$sawProvidersLine = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -notmatch '^\s*AI_PROVIDERS_JSON\s*=\s*(.*)$') { continue }
    $sawProvidersLine = $true
    $jsonRaw = $matches[1].Trim()
    if ([string]::IsNullOrWhiteSpace($jsonRaw)) { continue }

    $providers = $null
    try {
        $providers = $jsonRaw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        Write-Warning 'AI_PROVIDERS_JSON is not valid JSON; replacing the whole line with the canonical local-Ollama config.'
        $canonical = '[{"provider_id":"local-ollama","kind":"openai","model":"llama3.2","base_url":"' + $IntendedUrl + '","api_key":"","temperature":0.0,"max_tokens":2048,"streaming_enabled":true,"timeout_seconds":120}]'
        $lines[$i] = "AI_PROVIDERS_JSON=$canonical"
        $fixedAny  = $true
        continue
    }

    # Force to an array so a single-element JSON array iterates correctly.
    $providerList = @($providers)
    $changed = $false
    foreach ($p in $providerList) {
        $current = [string]$p.base_url
        if (Test-GoodBaseUrl $current) { continue }   # leave valid URLs alone
        if (-not (Test-LocalOllama $current)) {
            Write-Warning ("  provider '{0}' has a malformed base_url that is NOT the local Ollama host - left unchanged to avoid breaking another provider: {1}" -f $p.provider_id, $current)
            continue
        }
        Write-Host ("  provider '{0}' base_url repaired:" -f $p.provider_id) -ForegroundColor Yellow
        Write-Host "      from: $current" -ForegroundColor DarkGray
        Write-Host "      to  : $IntendedUrl" -ForegroundColor Green
        $p.base_url = $IntendedUrl
        $changed = $true
    }

    if ($changed) {
        $newJson = Convert-ProvidersToCompactJsonArray $providerList
        $lines[$i] = "AI_PROVIDERS_JSON=$newJson"
        $fixedAny  = $true
    }
}

# --- Step 4: if there was no AI_PROVIDERS_JSON line at all, append one --
if (-not $sawProvidersLine) {
    $canonical = '[{"provider_id":"local-ollama","kind":"openai","model":"llama3.2","base_url":"' + $IntendedUrl + '","api_key":"","temperature":0.0,"max_tokens":2048,"streaming_enabled":true,"timeout_seconds":120}]'
    $lines += "AI_PROVIDERS_JSON=$canonical"
    $fixedAny = $true
    Write-Host 'Added missing AI_PROVIDERS_JSON line (canonical local-Ollama config).' -ForegroundColor Yellow
}

# --- Step 5: ensure AI_DEFAULT_PROVIDER matches the provider id ---------
$sawDefault = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*AI_DEFAULT_PROVIDER\s*=') {
        $sawDefault = $true
        if ($lines[$i] -notmatch 'local-ollama') {
            $lines[$i] = 'AI_DEFAULT_PROVIDER=local-ollama'
            $fixedAny  = $true
            Write-Host 'AI_DEFAULT_PROVIDER set to local-ollama.' -ForegroundColor Yellow
        }
    }
}
if (-not $sawDefault) {
    $lines += 'AI_DEFAULT_PROVIDER=local-ollama'
    $fixedAny = $true
    Write-Host 'Added missing AI_DEFAULT_PROVIDER=local-ollama.' -ForegroundColor Yellow
}

# --- Step 6: write back (UTF-8, no BOM) ---------------------------------
if ($fixedAny) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($EnvFile, $lines, $utf8NoBom)
    Write-Host ''
    Write-Host 'backend/.env updated successfully.' -ForegroundColor Green
}
else {
    Write-Host ''
    Write-Host 'Nothing to repair - backend/.env already had a clean base_url.' -ForegroundColor Green
}

# --- Step 7: verification report ----------------------------------------
Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ' Verification - current backend/.env AI settings' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
$envContent = @(Get-Content -LiteralPath $EnvFile)
foreach ($name in 'AI_ENABLED', 'AI_CHAT_ENABLED', 'AI_QA_ENABLED', 'AI_DEFAULT_PROVIDER', 'AI_PROVIDERS_JSON') {
    $hit = $envContent | Where-Object { $_ -match ('^\s*' + $name + '\s*=') } | Select-Object -First 1
    if ($hit) {
        $val = $hit -replace ('^\s*' + $name + '\s*=\s*'), ''
        Write-Host ("{0,-22} = {1}" -f $name, $val)
    }
    else {
        Write-Host ("{0,-22} = <not set>" -f $name) -ForegroundColor DarkGray
    }
}

# Validate the final AI_PROVIDERS_JSON parses and every base_url is well-formed.
$finalLine = $envContent | Where-Object { $_ -match '^\s*AI_PROVIDERS_JSON\s*=' } | Select-Object -First 1
$finalJson = ''
if ($finalLine) { $finalJson = ($finalLine -replace '^\s*AI_PROVIDERS_JSON\s*=\s*', '').Trim() }
if ($finalJson) {
    try {
        $final = @(ConvertFrom-Json $finalJson -ErrorAction Stop)
        $ok = $true
        foreach ($p in $final) {
            if (-not (Test-GoodBaseUrl([string]$p.base_url))) {
                Write-Host ("  STILL MALFORMED: provider '{0}' base_url = {1}" -f $p.provider_id, $p.base_url) -ForegroundColor Red
                $ok = $false
            }
        }
        if ($ok) {
            Write-Host ''
            Write-Host 'RESULT: AI_PROVIDERS_JSON is valid JSON and every base_url is well-formed.' -ForegroundColor Green
        }
    }
    catch {
        Write-Host "RESULT: AI_PROVIDERS_JSON is still not valid JSON - inspect $EnvFile and the backup." -ForegroundColor Red
    }
}

Write-Host ''
Write-Host 'Next: restart the backend (docker compose restart / your run command),' -ForegroundColor Cyan
Write-Host 'then open http://localhost:3000/chat and send a message.' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
