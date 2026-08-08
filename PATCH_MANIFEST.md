# AcademicOS M13.2 — Incremental Patch Manifest (Document Enrichment)

**Baseline:** `96599be` (M13.1.1) · **Commit:** `b52f7f0` · **Date:** 2026-08-08
**Scope:** the first production use of structured generation — `POST /api/v1/ai/enrich`. No new retrieval/persistence/embedding/search/transport/provider/AI Core/prompt framework.

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/application/use_cases/ai/enrich_document.py` | `EnrichDocumentUseCase` — permission → extracted text → truncate → structured prompt → `structured_generate()` → validate → result. Honest fallback. |
| `backend/app/tests/unit/test_enrich_document.py` | 15 unit tests (permission, text source, success, structured validation, truncation, fallback, provenance). |
| `backend/app/tests/integration/test_ai_enrich_api.py` | 7 integration tests (flag off, auth, master switch gate, 404/422 error mapping). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/core/config.py` | `ai_enrichment_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"enrichment"` feature flag in `AiConfigView`. |
| `backend/app/application/dtos/ai.py` | `EnrichmentResult` DTO + `enrichment_result_dict` serializer; registered in `__all__`. |
| `backend/app/api/routes/ai.py` | `POST /ai/enrich` + `EnrichBody` / `EnrichmentResponseModel`; gated via `core.config.enabled AND feature_flags["enrichment"]`. |
| `backend/app/tests/unit/test_ai_config_view.py` | `_StubSettings` + expected flag dict include `enrichment`. |

## Reuse map (constraints honoured)
- `AiCore` (single composition authority) · `LanguageModelGateway.structured_generate()` (M11.3, first production use)
- `DocumentAnnotationService` + `GetIntakeExtractedTextUseCase` (existing intake/extracted-text pipeline)
- `PermissionEvaluator` (READ) · existing DTO patterns (`StructuredGenerationPrompt`/`Result`)
- existing error handling (404/403/422) · existing permission handling · existing AI fallback behaviour

## Not introduced
new retrieval pipeline · new persistence model · new embedding system · new search implementation · new transport owner · new provider abstraction · new AI Core · new prompt framework.

## Verification
- Backend: **1484 passed, 2 skipped** (+22 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean on changed files
