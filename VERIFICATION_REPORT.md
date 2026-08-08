# Verification Report — Sprint M14 (Search Reliability)

**Parent commit:** `3401be6` · **Commit:** `2eb8341` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Scope:** frontend-only search reliability fix.

---

## 1. Root cause (traced, not assumed)

End-to-end trace of the Search request lifecycle:

**Frontend:** `SearchPage` debounces the query (300 ms) → `run(text)` aborts any in-flight request via `controllerRef.current?.abort()`, creates a new `AbortController`, and calls `searchObjects({text}, {signal})`.

**Client (`lib/api/client.ts`):** when the caller's signal aborts, it links the external signal to an internal controller; the `fetch` rejects and the catch converts it to `throw new ApiError("Request cancelled.", { kind: "aborted" })`. Crucially this is an `ApiError` whose `.name === "ApiError"` — **not** a `DOMException` with `name === "AbortError"`.

**Defect:** `SearchPage`'s catch was `if ((err as Error).name === "AbortError") return;` — that is **false** for the `ApiError`, so the abort fell through to `setError(toErrorMessage(err))` and the literal **"Request cancelled."** was rendered to the user. (The empty-result path was already correct; "No results for energy" is legitimate when nothing matches.)

**Secondary race:** a superseded request's `finally { setLoading(false) }` could clear the active request's spinner, and a stale resolved result could briefly overwrite the latest query.

Reproduced deterministically: a regression test that makes `searchObjects` reject with `ApiError("Request cancelled.", { kind: "aborted" })` **fails on the pre-fix code** (the message is shown) and **passes after the fix**.

## 2. Fix (smallest correct)

`SearchPage.run()` — two changes, both justified by the traced failure:
1. Use the client's existing **`isAbortError(err)`** helper (handles both the `ApiError` aborted-kind **and** the `DOMException` AbortError shapes). Intentional cancellations stay silent → "Request cancelled." can no longer surface.
2. Guard `setHits` / `setError` / `setLoading` with **`controllerRef.current === controller`** → only the latest request publishes state (latest-query-wins, no stale-result overwrite, no loading clobber).

No backend change. No new abstraction — `isAbortError` already existed in the client; `SearchPage` just wasn't using it.

## 3. Search contract verification (Phase 5)

| # | Contract | Result |
|---|---|---|
| A | Valid query → results | ✅ `shows results for a matching query` |
| B | No results → clean empty state, NOT "Request cancelled." | ✅ `shows a clean empty state` |
| C | Intentional stale cancellation → silent, no overwrite | ✅ abort-suppressed tests (both shapes) + latest-query-wins |
| D | Genuine backend failure → clear error | ✅ `shows a genuine backend error` |
| E–J | Auth, permission, semantic on/off, Qdrant/embedder failure | ✅ backend unchanged (1538 tests); UI shows results/empty/error generically |
| K | Rapid typing → latest query wins | ✅ latest-query-wins test |
| L | Slow response → no stale overwrite | ✅ latest-query-wins (stale resolve discarded) |
| M | Repeated identical queries → consistent | ✅ guarded state replacement |
| N | Clearing search → correct empty state | ✅ unchanged `else` branch (debounced.trim() empty) |

## 4. Final independent audit (as if not authored)

| # | Check | Result |
|---|---|---|
| 1 | Root cause actually fixed? | ✅ `isAbortError` handles both abort shapes |
| 2 | Cancellation behaviour correct? | ✅ silent |
| 3 | Latest-query-wins guaranteed? | ✅ controller guard |
| 4 | No stale results? | ✅ guard skips superseded setHits |
| 5 | Empty results ≠ cancellation? | ✅ empty → `setHits([])`/`setSearched(true)`; cancel → silent |
| 6 | Genuine errors ≠ cancellation? | ✅ `isAbortError` → silent; else → setError |
| 7 | Permissions preserved? | ✅ backend unchanged (SearchObjectsUseCase R4 gate intact) |
| 8 | Semantic search preserved? | ✅ backend unchanged |
| 9 | Lexical search preserved? | ✅ backend unchanged |
| 10 | Qdrant failure safe? | ✅ backend graceful degradation unchanged |
| 11 | Embedder failure safe? | ✅ backend unchanged |
| 12 | M11/M12 behaviour preserved? | ✅ architecture 16/16 |
| 13 | Architecture boundaries? | ✅ no new infra |
| 14 | No duplicate infrastructure? | ✅ |
| 15 | No unnecessary files? | ✅ only the new test file |
| 16 | No debug code? | ✅ verified (no console/debugger/alert) |
| 17 | No secrets? | ✅ |
| 18 | No dead code? | ✅ |
| 19 | No generated junk? | ✅ |
| 20 | No missing tests? | ✅ defect repro + contract coverage |

**Findings:** Production-critical: **0**. Non-critical: **0**. Optional: an unmount-abort cleanup is not added (not the reported symptom; React 18 does not warn on post-unmount setState) — left minimal.

## 5. Test execution (actual)

| Suite | Result |
|---|---|
| Frontend Vitest | **76 passed** (70 → 76; +6 SearchPage) |
| TypeScript `tsc --noEmit` | **exit 0** |
| `next build` | success |
| Architecture guardrails | **16/16** |
| Backend full suite | **1538 passed, 2 skipped, 0 failed** (unchanged) |
| Backend search-targeted (semantic activation + embedding adapter) | passed |

## 6. Repository integrity
- Changed: `SearchPage.tsx` (+14/−3), `SearchPage.test.tsx` (new). **No backend files changed.**
- No debug code, no secrets, no dead code, no generated junk.
- Working tree clean after commit; branch `feature/m11-ai-workspace`.

## 7. Deliverables
- **Patch ZIP:** `releases/m14/m14-patch.zip`
- **Patch diff:** `releases/m14/m14.patch` (parent `3401be6` → `2eb8341`)
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M14 entry prepended)
