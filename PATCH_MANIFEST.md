# AcademicOS M12.2.1 — Incremental Patch Manifest (Embedding Contract Hardening)

**Baseline:** `8ef3ac2` (M12.2) · **Commit:** `51edb6a` · **Date:** 2026-08-08

## Files Modified

| Path | Change |
|---|---|
| `backend/app/infrastructure/ai/embedding/openai_embedding_adapter.py` | `_validate_dimensions()` after `_parse()`: rejects mismatched vector length. |
| `backend/app/infrastructure/ai/provider_factory.py` | Embedding config filter: `embedding_dimensions > 0` required for real adapter. |
| `backend/app/tests/unit/test_embedding_adapter.py` | +7 regression tests (dimension mismatch, missing/zero/negative fallback, valid config). |

## Verification
- Backend: **1437 passed, 2 skipped** · Architecture: **16/16** · ruff clean.
