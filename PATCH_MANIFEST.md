# AcademicOS M11.3 — Incremental Patch Manifest (AI Core Configuration Authority & OpenAI Hardening)

**Milestone:** M11.3 (AI Core = single production authority; OpenAI adapter production-ready)
**Baseline:** `01a9f04` (M11.2.1)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `60a0bc6` (code + tests) · docs/manifest on top
**Date:** 2026-08-07

**Scope:** AI Core becomes the authoritative owner of provider/model/config/
credentials/base-URL/generation-policy/selection; the assistant no longer
constructs a `ProviderConfig`; the OpenAI transport is hardened to production
grade. No RAG/embeddings/memory/agents/chat-UI. Fully backward compatible: no
schema change, no new dependencies, no new settings required.

---

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/architecture/test_ai_config_authority.py` | Guardrail: `ProviderConfig(...)` may be constructed only inside the AI Core. |
| `backend/app/tests/unit/test_openai_adapter_hardening.py` | 13 tests for the hardened adapter (policy body, accounting, structured output, client lifecycle, capability reporting). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/ai/core.py` | `AiCore` is provider-id-keyed with `select_provider` + `gateway`; health projects the 5 discovery kinds (API shape preserved). |
| `backend/app/infrastructure/ai/provider_factory.py` | `build_ai_core` builds the catalogue from `AI_PROVIDERS_JSON` (authoritative) + DEPRECATED `ASSISTANT_*` synthesis; `build_gateway_from_params` is the config-authority seam. |
| `backend/app/infrastructure/ai/llm/openai.py` | Production hardening: reused client + `close()`, `max_tokens`/`temperature` from config, parsed `finish_reason`/`usage`, measured latency, implemented `structured_generate`, accurate capabilities. |
| `backend/app/infrastructure/assistant/provider_factory.py` | `build_assistant_provider` composes the translator over an AI-Core gateway (no `ProviderConfig`); legacy `build_provider` removed. |
| `backend/app/infrastructure/llm/llm_provider.py` | Legacy test-injection ctor delegates config construction to the AI Core (`build_gateway_from_params`). |
| `backend/app/application/use_cases/assistant/ask_question.py` | Selection via `AiCore` (`select_provider`/`gateway`); `registry`/`ModelRegistry` retired from the use case. |
| `backend/app/api/routes/assistant.py` | Route consumes AI Core; per-conversation factory bound to `ai_core`; unknown provider -> 422. |
| `backend/app/application/services/model_registry.py` | Clearly DEPRECATED (isolated; not on the production path). |
| `backend/app/tests/unit/test_llm_pipeline.py`, `test_assistant_llm_api.py`, `test_model_registry.py` | Selection tests migrated to AI Core; retired build_provider tests. |

## Files Deleted

*(none)*

## Database Migrations

*(none)* — schema-free.

## New Dependencies

*(none)* — no SDKs, no new packages.

## Environment Variable Changes

*(none required for existing behaviour.)* `AI_PROVIDERS_JSON` is now the
authoritative provider config; legacy `ASSISTANT_*` still works (deprecated).

## Post-Apply Commands

```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification (this patch)

- Backend: **1366 passed, 2 skipped** (zero regressions)
- Frontend: **70 vitest passed (15 files)** · `tsc --noEmit` clean
- Architecture guardrails: **15/15**
- `ruff check --select F401,I001` clean on changed files; app boots (264 routes)
