# AcademicOS M12.1.1 — Incremental Patch Manifest (Configuration Authority Fix)

**Baseline:** `8232ee0` (M12.1) · **Commit:** `7712ce6` · **Date:** 2026-08-08

## Files Modified

| Path | Change |
|---|---|
| `backend/app/api/routes/ai.py` | Summarization gate: `settings.ai_summarization_enabled` → `core.config.enabled and core.config.feature_flags["summarization"]`. Removed unused `settings` import. |
| `backend/app/tests/integration/test_ai_summarize_api.py` | +3 master-switch regression tests. |

## Verification
- Backend: **1416 passed, 2 skipped** · Architecture: **16/16** · ruff clean.
