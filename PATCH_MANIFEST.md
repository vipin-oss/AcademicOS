# AcademicOS M12.3.1 — Incremental Patch Manifest (Semantic Search Config Authority Fix)

**Baseline:** `f0238c6` (M12.3) · **Commit:** `01c1a6f` · **Date:** 2026-08-08

## Files Modified

| Path | Change |
|---|---|
| `backend/app/api/routes/search.py` | `get_embedder()`: `settings.ai_semantic_search_enabled` → `ai_core.config.enabled and ai_core.config.feature_flags["semantic_search"]`. |
| `backend/app/tests/integration/test_semantic_search_activation.py` | +3 master-switch regression tests. |

## Verification
- Backend: **1444 passed, 2 skipped** · Architecture: **16/16** · ruff clean.
