# AcademicOS M12.3 — Incremental Patch Manifest (Semantic Search Activation)

**Baseline:** `70500b6` (M12.2.1) · **Commit:** `4fcf5ca` · **Date:** 2026-08-08

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/integration/test_semantic_search_activation.py` | 4 integration tests (flag off/on, AI Core resolution, graceful fallback). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/core/config.py` | `ai_semantic_search_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"semantic_search"` feature flag in `AiConfigView`. |
| `backend/app/api/routes/search.py` | `get_embedder()` resolves AI Core; `get_vector_repository()` uses same embedder; sync inherits via DI. |
| `backend/app/tests/unit/test_ai_config_view.py` | Expected flags include `"semantic_search"`. |

## Verification
- Backend: **1441 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
