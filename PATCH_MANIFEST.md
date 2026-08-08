# AcademicOS M14.1 — Incremental Patch Manifest (Search Results — Read-Time Index Repair)

**Parent commit:** `2561cb8` (M14) · **Commit:** `aeaaa8f` · **Date:** 2026-08-08
**Scope:** search reliability — backend-only. No new abstractions, no architecture change.

## Files Added
| Path | Purpose |
|---|---|
| `backend/app/tests/integration/test_search_read_repair.py` | 5 tests proving a newly created document is searchable via `GET /search` with NO manual sync; clean empty state; repeated stability; no-op on empty outbox. |

## Files Modified
| Path | Change |
|---|---|
| `backend/app/api/routes/search.py` | `GET /search` drains pending outbox events (existing `SearchIndexApplier`) before querying — read-time repair. +13 lines. |
| `backend/app/tests/integration/test_search_api.py` | `test_update_reflects_new_version_*` updated: the old "stale until sync" assertion encoded the bug; now asserts read-repair (search reflects committed writes immediately). |

## Root cause
The lexical search projection (`search_documents`) is derived from durable outbox events, but the system ships **no always-on outbox relay** — only intake-commit and manual `/search/index/sync` drain it. So the projection stayed empty in normal operation and `/search` returned no results for every query. (Reproduced: document invisible until drain; found after.)

## Reuse (constraints honoured)
Existing `SearchIndexApplier` + outbox relay + the same embedder/vector the semantic leg uses. No second search system / embedding abstraction / vector repo / provider / transport owner / AI Core / persistence. AiCore remains configuration authority. M11/M12/M13 + architecture guardrails unchanged (16/16). `/search` response shape, permission model, and semantic/lexical behaviour unchanged.

## Verification
- Backend: **1543 passed, 2 skipped** (+5 new; zero regressions)
- Architecture guardrails: **16/16** · ruff clean
- Frontend Vitest: **76 passed** · `tsc --noEmit` exit 0 (backend-only — unaffected)
