# AcademicOS M11.3.2 — Incremental Patch Manifest (Final Production Contract Hardening)

**Milestone:** M11.3.2 (unified runtime identity, three-state health, AI Core lifecycle ownership)
**Baseline:** `0afde47` (M11.3.1)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `341b743`
**Date:** 2026-08-07

**Scope:** Production-contract hardening only. No architecture redesign, no new
capabilities, no new SDKs. Backward compatible (additive health fields; no
schema/dependency/required-settings change).

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/ai/core.py` | `model_records` uses effective default; `executable` readiness; `AiCore.close()` lifecycle ownership. |
| `backend/app/application/dtos/ai.py` | `ProviderHealth`/`ProviderRecord` add `executable` + `operational`; serialization. |
| `backend/app/infrastructure/ai/llm/openai.py`, `placeholders.py` | `health()` reports configured(declared)/executable/operational. |
| `backend/app/api/routes/ai.py` | `AiProviderResponseModel` exposes `executable` + `operational`. |
| `backend/app/api/dependencies/ai.py` | `get_ai_core` lazy singleton (consistent lifecycle) + `reset_ai_core_cache()`. |
| `backend/app/infrastructure/ai/provider_factory.py`, `infrastructure/llm/llm_provider.py` | Deprecation notes on the isolated compatibility seam. |
| `backend/app/tests/...` | three-state health + lifecycle + identity-agreement tests; fake updated. |
| `frontend/src/types/index.ts`, `AiSettingsView.tsx(.test)` | `executable`/`operational`; readiness badge uses `executable`. |
| `README.md`, `AI_DEVELOPER_GUIDE.md` | Corrected to match the implementation. |

## Files Added
*(none — tests appended to existing files)*

## Database Migrations / Dependencies / Settings
*(none required)*

## Post-Apply
```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification
- Backend: **1387 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
