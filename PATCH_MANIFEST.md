# AcademicOS M11.3.3 — Incremental Patch Manifest (Final Runtime Hardening)

**Milestone:** M11.3.3 (assistant executable readiness, thread-safe singleton, FastAPI lifecycle)
**Baseline:** `f8d7b2e` (M11.3.2)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `e09c944`
**Date:** 2026-08-08

**Scope:** Final runtime hardening. No architecture redesign, no new capabilities.
Backward compatible (no API/schema/deps change).

## Files Modified

| Path | Change |
|---|---|
| `backend/app/infrastructure/assistant/provider_factory.py` | `_gateway_ready` uses `.executable` (can run), not `.configured` (declared). |
| `backend/app/api/dependencies/ai.py` | Thread-safe singleton (double-checked locking); locked + idempotent `reset_ai_core_cache`. |
| `backend/app/main.py` | FastAPI `lifespan` handler: shutdown closes AI Core gateway resources via `reset_ai_core_cache()`. |

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/unit/test_m11_3_3_runtime_guardrails.py` | 7 behaviour tests: non-executable never primary, lifecycle shutdown, singleton concurrency, idempotent reset. |

## Post-Apply
```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification
- Backend: **1392 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
