# AcademicOS M12.1 — Incremental Patch Manifest (Document Summarization)

**Milestone:** M12.1 (POST /ai/summarize — on-demand document summary)
**Baseline:** `e33246d` (M11.3.4 frozen)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `e1e445c`
**Date:** 2026-08-08

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/application/use_cases/ai/summarize_document.py` | `SummarizeDocumentUseCase` (permission, text, truncation, prompt, generate, fallback). |
| `backend/app/tests/unit/test_summarize_document.py` | 9 unit tests (permission, text, truncation, delimiters, fallback). |
| `backend/app/tests/integration/test_ai_summarize_api.py` | 4 integration tests (flag, auth, 404, 422). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/core/config.py` | `ai_summarization_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"summarization"` feature flag in `AiConfigView`. |
| `backend/app/application/exceptions.py` | `PermissionDeniedError(ApplicationError)`. |
| `backend/app/application/dtos/ai.py` | `SummarizeResult` DTO + `summarize_result_dict` serializer. |
| `backend/app/api/routes/ai.py` | `POST /ai/summarize` endpoint + `SummarizeBody` / `SummarizeResponseModel`. |
| `backend/app/tests/unit/test_ai_config_view.py` | Expected flags include `"summarization"`. |

## Post-Apply
```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
# Enable: set AI_SUMMARIZATION_ENABLED=true in .env
```

## Verification
- Backend: **1413 passed, 2 skipped** · Architecture: **16/16** · ruff clean.
