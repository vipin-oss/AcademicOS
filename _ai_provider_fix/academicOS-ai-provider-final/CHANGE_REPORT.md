# Root Cause & Fix Report

## A. Root cause
AI_PROVIDERS_JSON defaulted to "" (empty). With no providers configured,
OpenAIProvider had no base_url → `_is_configured` returned False → every AI
endpoint returned "AI is not configured." The OllamaProvider and LocalProvider
classes are honest placeholders (always "not_configured") — they are NOT real
adapters. The REAL local adapter is `OpenAIProvider` (kind="openai") pointed at
any OpenAI-compatible endpoint.

## B. Local provider/model selected
- Provider: OpenAIProvider with base_url=http://localhost:11434/v1 (Ollama's OpenAI-compatible API)
- Model: llama3.2 (lightweight, 3B params, pulls in ~2 GB)
- No API key required (api_key="")
- No paid service invoked

## C. Files changed (2)
1. `docker-compose.yml` — added `ollama` service (port 11434, named academicos-ollama)
2. `backend/.env.example` — pre-configured AI_PROVIDERS_JSON + all feature flags ON

## D. Tests passed
- Backend: 1591 passed, 2 skipped, 0 failed
- Frontend: 76 passed (16 files)
- Build: success
- TypeScript: exit 0
