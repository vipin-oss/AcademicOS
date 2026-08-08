# AcademicOS M13.1 — Incremental Patch Manifest (Grounded QA)

**Baseline:** `0a0c0c7` (M12.3.1) · **Commit:** `92707e8` · **Date:** 2026-08-08

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/application/use_cases/ai/grounded_qa.py` | `GroundedQAUseCase` (sync + streaming). |
| `backend/app/tests/integration/test_ai_qa_api.py` | 5 integration tests (flag, auth, master switch, 422, streaming). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/core/config.py` | `ai_qa_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"qa"` feature flag. |
| `backend/app/application/dtos/ai.py` | `QAResult` DTO + `qa_result_dict` serializer. |
| `backend/app/api/routes/ai.py` | `POST /ai/qa` + `POST /ai/qa/stream` + response models. |
| `backend/app/tests/architecture/test_ai_guardrails.py` | Use cases may compose assistant services. |
| `backend/app/tests/unit/test_ai_config_view.py` | Expected flags include `"qa"`. |

## Verification
- Backend: **1444 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
