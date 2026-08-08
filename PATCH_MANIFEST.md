# AcademicOS M14 — Incremental Patch Manifest (Search Reliability)

**Parent commit:** `3401be6` (post-audit HEAD) · **Commit:** `2eb8341` · **Date:** 2026-08-08
**Scope:** search reliability — frontend-only. No backend/search-infra change, no new abstractions.

## Files Added
| Path | Purpose |
|---|---|
| `frontend/src/components/features/search/SearchPage.test.tsx` | 6 component regression tests: matching query, clean empty state, abort suppressed (ApiError + DOMException shapes), latest-query-wins (stale-result discarded), genuine error shown. |

## Files Modified
| Path | Change |
|---|---|
| `frontend/src/components/features/search/SearchPage.tsx` | `run()` uses `isAbortError()` (both abort shapes) instead of `err.name === "AbortError"`; state updates guarded by `controllerRef.current === controller` (latest-query-wins). +14/−3. |

## Root cause
`SearchPage` misclassified the client's abort error. The shared client throws `ApiError("Request cancelled.", { kind: "aborted" })` (`name === "ApiError"`) on a caller-aborted request; `SearchPage` only checked the `DOMException` shape (`name === "AbortError"`), so the abort leaked to `setError` and displayed **"Request cancelled."** The client already exported a correct `isAbortError()` helper — `SearchPage` simply didn't use it.

## Reuse (constraints honoured)
No second search system / embedding abstraction / vector repository / provider / transport owner / AI Core / persistence. AiCore remains configuration authority. M11/M12 architecture guardrails unchanged (16/16). Backend `/search` contract unchanged.

## Verification
- Frontend Vitest: **76 passed** (+6)
- TypeScript `tsc --noEmit`: **exit 0** · `next build`: success
- Backend: **1538 passed, 2 skipped** (unchanged) · Architecture: **16/16**
