# AcademicOS M11.1 — Incremental Patch Manifest (AI Foundation)

**Milestone:** M11.1 (AI Core — infrastructure only)
**Baseline:** `4d3c4cd` (M10 Release Candidate 1 — frozen)
**Branch:** `feature/m11-ai-workspace`
**Patch commits:** `abfbb92` (AI application layer) · `7a6a986` (placeholders + DI + health API) · `194c8fa` (AI guardrails) · `04248aa` (AI Settings page) · `80083fc` (docs) · manifest on top
**Date:** 2026-08-07

**Scope:** AI infrastructure only. No chat, no RAG, no memory, no agents,
no embeddings, no LLM calls, no API keys, no network requests. The system
behavior is unchanged — every provider reports "Not Configured" until a
real adapter lands in a later M11 sprint.

Apply over any M10 RC1 installation. Fully backward compatible: additive
packages, new routes, new settings (all with defaults that preserve
existing behavior), zero changes to existing contracts.

---

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/application/ai/__init__.py` | AI Core package |
| `backend/app/application/ai/errors.py` | `AiError` / `AiNotConfiguredError` / `UnknownProviderError` (application-layer, framework-free) |
| `backend/app/application/ai/config.py` | `AiConfigView` — AI settings projection + feature flags |
| `backend/app/application/ai/core.py` | `AiCore` facade — health/providers/models aggregation + gateway lookup |
| `backend/app/application/ai/llm/__init__.py` | LLM capability package |
| `backend/app/application/ai/llm/ports.py` | `LanguageModelGateway` protocol (6 operations) |
| `backend/app/application/ai/llm/estimates.py` | Deterministic token/cost estimation |
| `backend/app/application/ai/providers/__init__.py` | Providers package |
| `backend/app/application/ai/providers/config.py` | `AI_PROVIDERS_JSON` parsing (`parse_provider_configs`, `configs_by_kind`) |
| `backend/app/application/ai/providers/registry.py` | `ProviderRegistry` — kind→factory discovery |
| `backend/app/application/use_cases/ai/__init__.py` | AI use-case package |
| `backend/app/application/use_cases/ai/get_ai_health.py` | `GetAiHealthUseCase` |
| `backend/app/application/use_cases/ai/list_ai_providers.py` | `ListAiProvidersUseCase` |
| `backend/app/application/use_cases/ai/list_ai_models.py` | `ListAiModelsUseCase` |
| `backend/app/application/dtos/ai.py` | AI DTOs + validation + serialization helpers |
| `backend/app/infrastructure/ai/__init__.py` | AI adapters package |
| `backend/app/infrastructure/ai/provider_factory.py` | `build_ai_core` — the single composition root |
| `backend/app/infrastructure/ai/llm/__init__.py` | LLM adapters package |
| `backend/app/infrastructure/ai/llm/placeholders.py` | OpenAI / Anthropic / Google / Ollama / Local placeholders |
| `backend/app/api/dependencies/ai.py` | `get_ai_core` — test-overridable DI seam |
| `backend/app/api/routes/ai.py` | `GET /ai/health` (public) · `GET /ai/providers` · `GET /ai/models` (auth) |
| `backend/app/tests/unit/test_ai_dtos.py` | DTO validation tests |
| `backend/app/tests/unit/test_ai_estimates.py` | Estimate tests |
| `backend/app/tests/unit/test_ai_provider_config.py` | Config parsing tests |
| `backend/app/tests/unit/test_ai_registry.py` | Registry tests |
| `backend/app/tests/unit/test_ai_config_view.py` | Config view tests |
| `backend/app/tests/unit/test_ai_core.py` | Core aggregation + use-case tests |
| `backend/app/tests/unit/test_ai_placeholders.py` | Placeholder behavior tests |
| `backend/app/tests/integration/test_ai_health_api.py` | Full DI-chain API tests |
| `backend/app/tests/architecture/test_ai_guardrails.py` | 4 AI layering guardrails |
| `frontend/src/lib/api/ai.ts` | Typed AI health client |
| `frontend/src/components/features/settings/AiSettingsView.tsx` | AI Settings view |
| `frontend/src/components/features/settings/AiSettingsView.test.tsx` | 5 view tests |
| `frontend/src/app/(main)/settings/ai/page.tsx` | `/settings/ai` page |
| `AI_DEVELOPER_GUIDE.md` | Provider-adapter extension contract |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/core/config.py` | AI settings: `AI_ENABLED`, `AI_DEFAULT_PROVIDER`, `AI_DEFAULT_MODEL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS`, `AI_TIMEOUT_SECONDS`, `AI_STREAMING_ENABLED`, capability flags (all OFF), `AI_PROVIDERS_JSON` |
| `backend/app/main.py` | AI router mounted at `/api/v1/ai/*` (existing routers untouched) |
| `backend/.env.example` | AI configuration block with docs |
| `frontend/src/types/index.ts` | `AiHealth` / `AiModelInfo` / `AiProviderInfo` / response types |
| `frontend/src/components/layout/Sidebar.tsx` | "AI Settings" nav entry (`/settings/ai`) |
| `README.md` | AI Foundation section + layout tree |
| `CHANGELOG.md` | M11.1 entry |
| `AcademicOS_AI_Architecture.md` | Appendix G — M11.1 implementation status |
| `PATCH_MANIFEST.md` | This manifest |

## Files Deleted

*(none)*

## Database Migrations

*(none)* — M11.1 is schema-free.

## New Dependencies

*(none)* — no SDKs, no new packages. (The `psycopg2`-excluded install
procedure is unchanged.)

## Environment Variable Changes

New (all optional, defaults preserve existing behavior):

```
AI_ENABLED=true
AI_DEFAULT_PROVIDER=local
AI_DEFAULT_MODEL=
AI_TEMPERATURE=0.0
AI_MAX_TOKENS=2048
AI_TIMEOUT_SECONDS=30.0
AI_STREAMING_ENABLED=true
AI_CHAT_ENABLED=false
AI_RAG_ENABLED=false
AI_MEMORY_ENABLED=false
AI_AGENTS_ENABLED=false
AI_DOCUMENT_UNDERSTANDING_ENABLED=false
AI_PROVIDERS_JSON=
```

## Post-Apply Commands

```powershell
# No schema or dependency steps. Restart the backend:
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
# Frontend (if not already running):
cd frontend && npm run dev
```

## Verification (this patch)

- Backend suite: **1351 passed, 2 skipped (1242 baseline + 109 new AI tests)**
- Architecture guardrails: **11/11** (7 domain + 4 AI)
- Frontend: **70 passed (15 files)** (was 65) · `tsc --noEmit` clean · `next build` clean
- Manual API: `/api/v1/ai/health` 200 public · `/api/v1/ai/providers` + `/api/v1/ai/models` 401 without JWT / 200 with · `/api/v1/health` regression 200
