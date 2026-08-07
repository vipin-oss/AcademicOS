# AcademicOS M11.2.1 — Incremental Patch Manifest (Architecture Hardening — ADR-001)

**Milestone:** M11.2.1 (Architecture hardening — AI Core is the sole gateway-composition authority)
**Baseline:** `1c1d81f` (M11.2)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `56e9e18` (code + guardrails) · docs/manifest on top
**Date:** 2026-08-07

**Scope:** Architecture hardening ONLY. No behaviour change, no new providers,
no SDKs, no new user-facing functionality. Closes the AI Core bypass found by
the hostile audit of M11.2: the assistant no longer constructs a concrete
provider anywhere — all gateway creation flows through the AI Core's single
`build_gateway` constructor, and the invariants are machine-enforced.

Apply over any M11.2 installation. Fully backward compatible: no schema
change, no new dependencies, no new routes, no new settings. Every existing
call site and test passes unchanged.

---

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/architecture/test_ai_composition_authority.py` | Two guardrails: (1) no feature module imports a concrete provider class; (2) the module-level `build_gateway` is defined only in the composition root. |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/infrastructure/ai/provider_factory.py` | NEW `build_gateway(config, *, kind, client, retry_attempts, retry_backoff_seconds)` — the SINGLE gateway constructor (only place a concrete provider is imported/instantiated); re-exports `LlmProviderError`/retry constants. `build_ai_core` builds the catalogue through it. |
| `backend/app/application/ai/core.py` | NEW `AiCore.build_gateway(config)` — the application-pure seam features consume (delegates to the registry). Imports `ProviderConfig`. |
| `backend/app/infrastructure/assistant/provider_factory.py` | `build_provider` obtains the gateway via `ai_core.build_gateway` (or `build_gateway` for the ai_core-less path); no longer imports `OpenAIProvider`. |
| `backend/app/infrastructure/llm/llm_provider.py` | Legacy constructor obtains its gateway via `build_gateway`; imports from the composition root instead of the concrete provider module; no longer names `OpenAIProvider`. |
| `backend/app/api/routes/assistant.py` | `get_assistant_provider_factory` is bound to `ai_core`, so per-conversation model selection also flows through the AI Core. |
| `backend/app/tests/architecture/test_transport_ownership.py` | Broadened from `infrastructure/llm` to ALL feature layers (AI catalogue, assistant, application, api); httpx permitted only in `infrastructure/ai/llm/openai.py`. |

## Files Deleted

*(none)*

## Database Migrations

*(none)* — schema-free.

## New Dependencies

*(none)*

## Environment Variable Changes

*(none)*

## Post-Apply Commands

```powershell
# No schema or dependency steps. Restart the backend:
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification (this patch)

- Backend suite: **1354 passed, 2 skipped** (M11.2 baseline 1352 + 2 new composition guardrails; **zero regressions**)
- Architecture guardrails: **14/14** (7 domain + 4 AI + 1 transport-ownership + 2 composition-authority)
- Hostile-audit re-check (independent AST scan): no feature imports a concrete provider; one module-level `build_gateway`; httpx only in `infrastructure/ai/llm/openai.py`
- `ruff check --select F401,I001` clean on changed files (B008 = FastAPI `Depends()` idiom, consistent with baseline)
- App boots; 264 routes registered; `AiCore.build_gateway` present; catalogue intact
