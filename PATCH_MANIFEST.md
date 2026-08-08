# AcademicOS M11.3.4 — Incremental Patch Manifest (Final Production Runtime Contract Fixes)

**Milestone:** M11.3.4 (health overclaim fix + streaming enforcement)
**Baseline:** `72248be` (M11.3.3)
**Branch:** `feature/m11-ai-workspace`
**Patch commit:** `a50516f`
**Date:** 2026-08-08

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | `HEALTH_CONFIGURED = "configured"` added; `HEALTH_OK` reserved (never used without probe). |
| `backend/app/application/ai/core.py` | `health_summary` status: `HEALTH_OK` → `HEALTH_CONFIGURED` (honest: executable, not verified). |
| `backend/app/infrastructure/ai/llm/openai.py` | `stream()` raises `LlmProviderError` when `streaming_enabled` is False. |
| `backend/app/infrastructure/ai/provider_factory.py` | `build_ai_core` ANDs global `AI_STREAMING_ENABLED` with per-provider configs. |
| `backend/app/tests/unit/test_ai_core.py`, `test_ai_runtime_contract.py` | Status assertions updated to `configured`. |
| `frontend/src/types/index.ts`, `AiSettingsView.tsx` | Health status type + badge updated for `configured`. |

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/unit/test_m11_3_4_contract_fixes.py` | 6 regression tests: health overclaim, streaming enforcement, sync unaffected. |

## Post-Apply
```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verification
- Backend: **1400 passed, 2 skipped** · Frontend: **70 vitest + tsc clean** · Architecture: **16/16** · ruff clean.
