# AcademicOS M11.2 — Incremental Patch Manifest (Architecture Alignment — ADR-001)

**Milestone:** M11.2 (Architecture alignment — unify LLM transport behind `LanguageModelGateway`)
**Baseline:** `1c0e82e` (M11.1 — AI Foundation)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `1755df2` (code + tests) · docs/manifest on top
**Date:** 2026-08-07

**Scope:** Architecture alignment ONLY. No behaviour change, no new providers,
no SDKs, no new user-facing functionality. The OpenAI-compatible transport is
relocated from `infrastructure/llm` to the AI Core's `LanguageModelGateway`
adapter (`infrastructure/ai/llm/openai.py`), which becomes the single owner of
generative-LLM transport. The assistant consumes the gateway instead of owning
transport. The deterministic rules provider and the fallback chain are
untouched.

Apply over any M11.1 installation. Fully backward compatible: no schema
change, no new dependencies, no new routes, no new settings required for
existing behaviour. `LlmAssistantProvider`'s public surface is preserved, so
every existing call site and test passes unchanged.

---

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/infrastructure/ai/llm/openai.py` | Real `OpenAIProvider` — implements `LanguageModelGateway`; the SINGLE owner of the OpenAI-compatible httpx transport (relocated verbatim from the former `LlmAssistantProvider` transport). Honest "not configured" surface when no `base_url`; real chat-completions when configured. Defines `LlmProviderError`. |
| `backend/app/tests/architecture/test_transport_ownership.py` | Guardrail: `infrastructure/llm` must not import httpx. Fails CI if the duplicate-transport regression returns. |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | `ProviderConfig.api_key` (credential seam — ADR-001 Q7.5); `GenerationPrompt.extra_body` (provider-agnostic extra request fields). Both additive, defaults preserve existing behaviour. |
| `backend/app/application/ai/providers/config.py` | `parse_provider_configs` reads the `api_key` field. |
| `backend/app/infrastructure/ai/llm/placeholders.py` | `OpenAIProvider` removed (moved to `openai.py`); the four honest placeholders (Anthropic / Google / Ollama / Local) remain. Unused `PROVIDER_KIND_OPENAI` import dropped. |
| `backend/app/infrastructure/ai/provider_factory.py` | `build_ai_core` registers the REAL `OpenAIProvider` for the `openai` kind (was the placeholder). |
| `backend/app/infrastructure/llm/llm_provider.py` | `LlmAssistantProvider` is now a thin translator over a `LanguageModelGateway` — no httpx, no retries, no wire format. Public surface preserved: `answer`/`stream`/`name`/`PROVIDER_NAME`/`LlmProviderError` (re-exported) and the legacy `(client, model, base_url, ...)` constructor (builds the gateway internally). |
| `backend/app/infrastructure/assistant/provider_factory.py` | `build_provider` constructs the `OpenAIProvider` gateway from the model spec (was: built an httpx client + transport directly) and wraps it; reads the AI Core's generation defaults via the optional `ai_core`. No longer imports httpx. |
| `backend/app/api/routes/assistant.py` | `get_assistant_provider` injects `get_ai_core` (the assistant consumes the AI Core seam). |
| `backend/app/tests/unit/test_ai_placeholders.py` | Imports `OpenAIProvider` from its new home (`openai.py`). |

## Files Deleted

*(none)*

## Database Migrations

*(none)* — M11.2 is schema-free.

## New Dependencies

*(none)* — no SDKs, no new packages. httpx was already a dependency.

## Environment Variable Changes

*(none required for existing behaviour.)* `AI_PROVIDERS_JSON` entries MAY now
include an optional `"api_key"` field (read only inside the gateway adapter,
never logged). The legacy `ASSISTANT_*` settings continue to drive the
assistant's model registry unchanged (config consolidation is M11.3).

## Post-Apply Commands

```powershell
# No schema or dependency steps. Restart the backend:
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification (this patch)

- Backend suite: **1352 passed, 2 skipped** (baseline 1351 + 1 new transport-ownership guardrail; **zero regressions**)
- Architecture guardrails: **12/12** (7 domain + 4 AI + 1 transport-ownership)
- `ruff check --select F401,I001` clean on every changed file (B008 = FastAPI `Depends()` idiom, consistent with baseline)
- App boots; 264 routes registered; `/api/v1/ai/health` 200 (public) · `/api/v1/assistant/*` unchanged
