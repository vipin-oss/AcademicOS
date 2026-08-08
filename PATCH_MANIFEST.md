# AcademicOS Full-System Audit (M11 → M13.3.1) — Remediation Manifest

**Pre-remediation:** `efbf0c6` · **Remediation commit:** `039b8c1` · **Date:** 2026-08-08

## Defect remediated
**QA route late-gate** — `POST /ai/qa` and `POST /ai/qa/stream` resolved `get_embedder`/`get_vector_repository` (via `Depends()`) before the handler-body feature gate. A disabled QA feature still resolved the AI embedder and provisioned/queried the Qdrant/vector collection. Fix: inline resolution after the gate (same pattern as the M13.3.1 `/ai/related` fix; same `get_embedder`/`get_vector_repository` as `/search`).

## Files changed
| Path | Change |
|---|---|
| `backend/app/api/routes/ai.py` | `/ai/qa` + `/ai/qa/stream` resolve embedder/vector inline after the gate (removed from `Depends()` signature). |
| `backend/app/tests/integration/test_ai_qa_api.py` | +4 regression tests (`TestFeatureGateResolutionOrder`): embedder/vector not resolved when `qa=false` / `AI_ENABLED=false` / on the stream endpoint; resolved once when enabled. |

## Files deleted (proven dead)
| Path | Evidence |
|---|---|
| `MigrationFix/backend/alembic.ini` | unreferenced; `alembic.ini` identical to active `backend/alembic.ini` |
| `MigrationFix/backend/alembic/env.py` | unreferenced; **differs** from active `backend/alembic/env.py` (stale) |
| `MigrationFix/backend/alembic/script.py.mako` | unreferenced duplicate |
| `MigrationFix/backend/alembic/versions/0001_initial.py` | unreferenced stale copy; active migrations live in `backend/alembic/versions/` |

Proof of safety: `grep -r MigrationFix` across `*.py/*.md/*.yml/*.ps1/*.sh/*.toml/*.ini/*.cfg` → 0 references; not in `docker-compose.yml`, `scripts/`, or CI; not imported; not required by tests/runtime.

## Not changed (intentional)
- `/search`, `/assistant`, `/intake` routes (always-on, graceful degradation — correctly unaffected).
- Release artifacts under `releases/` and root `*.patch` (workflow-required / not proven dead).
- Flaky intake test `test_pause_resume_completes_exactly_all_items` (pre-M11, timing-dependent, not a product defect; out of scope).

## Verification
- Backend: **1538 passed, 2 skipped, 0 failed** (+4 new)
- Architecture guardrails: **16/16**
- Frontend: 70 vitest · `tsc --noEmit` exit 0 · `next build` success (unaffected)
- Lint: clean on changed files
