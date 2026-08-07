# AcademicOS M11.3.1 — Incremental Patch Manifest (Production Correctness Hardening)

**Milestone:** M11.3.1 (provider/model identity contract, AI_DEFAULT_MODEL runtime, health correctness)
**Baseline:** `e7c1d8e` (M11.3)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `26cbc91`
**Date:** 2026-08-07

**Scope:** Production-correctness fixes only. No architecture redesign, no new
capabilities, no new SDKs. Fully backward compatible (no schema, dependency, or
required-settings change; `model_id` retained as a deprecated alias; legacy
conversation pins still resolved).

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/architecture/test_production_provider_isolation.py` | Guardrail: api/ and application/ never import the bypass constructors. |
| `backend/app/tests/unit/test_ai_runtime_contract.py` | Runtime contract tests: identity, multi-provider distinguishability, selection precedence, AI_DEFAULT_MODEL influence, health/runtime consistency. |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/infrastructure/ai/llm/openai.py` | `provider_id` is a property = the configured catalogue identity (distinct from `kind`). |
| `backend/app/infrastructure/ai/llm/placeholders.py` | Same `provider_id` property (config identity, falls back to kind for discovery). |
| `backend/app/application/ai/core.py` | Health rows keyed by provider_id (one per provider); health reports effective default + executability; `build_gateway` disabled; effective-default helpers. |
| `backend/app/infrastructure/ai/provider_factory.py` | `_resolve_default_provider_id` honours `AI_DEFAULT_MODEL`; authoritative settings precede legacy. |
| `backend/app/application/dtos/assistant.py` | `AskQuestionInput.provider_id` (+ `model_id` alias via `__post_init__`); `KEY_PROVIDER_ID`. |
| `backend/app/api/mappers/assistant_mapper.py` | Maps `provider_id` (with `model_id` alias). |
| `backend/app/api/routes/assistant.py` | `AskBody.provider_id`; eager validation uses `provider_id`. |
| `backend/app/application/use_cases/assistant/ask_question.py` | Selection/pin by `provider_id` (legacy key fallback read). |
| `backend/app/core/config.py` | Truthful `AI_DEFAULT_PROVIDER` / `AI_DEFAULT_MODEL` comments. |
| `backend/app/tests/...` (health, pipeline, assistant-llm) | Updated to the corrected contract (provider_id identity, effective-default validity, pin key). |
| `AI_DEVELOPER_GUIDE.md` | Identity/selection contract section; corrected config + health descriptions. |

## Database Migrations / Dependencies / Settings
*(none required)*

## Post-Apply
```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification
- Backend: **1379 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
