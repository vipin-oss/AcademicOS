# AcademicOS M20 — Confidence Indicators on QA Results
**Parent:** 79cd300 · **Commit:** (current) · **Date:** 2026-08-08
## Files Modified
| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | `confidence: str = ""` on QAResult + serializer. |
| `backend/app/application/use_cases/ai/grounded_qa.py` | `_compute_confidence` heuristic (finish_reason + retrieved_count + truncated). |
| `backend/app/api/routes/ai.py` | `confidence` on QAResponseModel + ChatResponseModel. |
| `backend/app/tests/unit/test_grounded_qa.py` | +4 confidence indicator tests. |
## Verification
- Backend: **1591 passed, 2 skipped** (+4; zero regressions) · Architecture **16/16**
