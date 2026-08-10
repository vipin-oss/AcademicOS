# APPLY STEPS — AcademicOS Local AI Provider Setup

## What this does
Adds Ollama to Docker Compose and pre-configures all AI settings so chat works
with a FREE local model (llama3.2, no API key needed).

## PowerShell — copy and paste ALL of this:

```powershell
cd E:\AcademicOS

# --- 1. Extract ---
Expand-Archive academicOS-ai-provider-final.zip -DestinationPath C:\temp\aiprovider

# --- 2. Copy docker-compose.yml (adds Ollama service) ---
Copy-Item "C:\temp\aiprovider\academicOS-ai-provider-final\files\docker-compose.yml" "docker-compose.yml" -Force

# --- 3. Copy .env.example ---
Copy-Item "C:\temp\aiprovider\academicOS-ai-provider-final\files\backend\.env.example" "backend\.env.example" -Force

# --- 4. Update your .env with AI provider settings ---
$envFile = "backend\.env"
$envContent = Get-Content $envFile -Raw -ErrorAction SilentlyContinue

# Remove any existing AI_ lines
if ($envContent) {
    $envContent = $envContent -replace '(?ms)^#.*AI Core.*$(?:\r?\n^AI_.*$)*', ''
    $envContent = $envContent -replace '(?ms)^AI_\w+.*$\r?\n', ''
    $envContent = $envContent.TrimEnd()
}

# Add the correct AI configuration
$aiConfig = @"

# ---- AI Core — Local/Free via Ollama ----
AI_ENABLED=true
AI_CHAT_ENABLED=true
AI_QA_ENABLED=true
AI_SUMMARIZATION_ENABLED=true
AI_ENRICHMENT_ENABLED=true
AI_RELATED_DOCUMENTS_ENABLED=true
AI_SEMANTIC_SEARCH_ENABLED=true
AI_STREAMING_ENABLED=true
AI_PROVIDERS_JSON=[{"provider_id":"local-ollama","kind":"openai","model":"llama3.2","base_url":"http://localhost:11434/v1","api_key":"","temperature":0.0,"max_tokens":2048,"streaming_enabled":true}]
AI_DEFAULT_PROVIDER=local-ollama
"@

$envContent + $aiConfig | Set-Content $envFile -Encoding UTF8
Write-Host "backend\.env updated with AI provider configuration"

# --- 5. Start Ollama container ---
docker compose up -d ollama
Write-Host "Waiting for Ollama to start..."
Start-Sleep -Seconds 10

# --- 6. Pull the model (FIRST TIME ONLY — takes 1-3 minutes) ---
Write-Host "Pulling llama3.2 model (this takes 1-3 minutes on first run)..."
docker exec academicos-ollama ollama pull llama3.2
Write-Host "Model pulled successfully."

# --- 7. Restart the backend (Ctrl+C in the backend terminal, then) ---
# In a NEW PowerShell terminal:
# cd E:\AcademicOS\backend
# python -m uvicorn app.main:app --reload --port 8000

# --- 8. Verify the provider is configured ---
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/ai/health" -UseBasicParsing | Select-Object -ExpandProperty Content

# --- 9. Test chat via the browser ---
# Open http://localhost:3000/chat and type: "number of research paper related to piezo"

# --- 10. Git commit and push ---
cd E:\AcademicOS
git add docker-compose.yml backend/.env.example
git commit -m "fix: add Ollama local AI provider + enable all AI feature flags"
git push origin feature/m11-ai-workspace
```

## If you already have Ollama running outside Docker
If you run Ollama natively (not via Docker), skip steps 5-6 and set the
base_url to `http://localhost:11434/v1` in your .env (it already is).

## Model alternatives
If llama3.2 is too slow, try a smaller model:
- `docker exec academicos-ollama ollama pull qwen2.5:0.5b` (fast, 0.5B)
- Then update `AI_PROVIDERS_JSON` in .env to use `"model":"qwen2.5:0.5b"`
