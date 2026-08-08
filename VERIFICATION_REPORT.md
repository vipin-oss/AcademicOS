# Verification Report — Sprint M14.1 (Search Results — Read-Time Index Repair)

**Parent commit:** `2561cb8` (M14) · **Commit:** `aeaaa8f` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Scope:** backend-only search reliability fix.

---

## 1. Root cause (traced end-to-end, then reproduced)

Full lifecycle traced: `SearchPage` → API client → `GET /api/v1/search` → `SearchObjectsUseCase` → lexical (`SQLAlchemySearchRepository`) + semantic → embedder → vector → permission filter → serializer → render.

**Where the result disappeared:** the lexical search matches against the derived `search_documents` projection table, **not** live objects. That projection is populated **only** by draining durable outbox events (`SearchIndexApplier.apply_pending`). The system ships **no always-on outbox relay** — only intake-commit and a manual `POST /search/index/sync` drain it. In normal operation the projection stayed **empty**, so `/search` returned `[]` for every query (including "energy") even though objects existed in the store.

**Reproduction (deterministic):**
- Create a document "Renewable Energy Systems" (with its outbox event, exactly as the creation use case does).
- `search_documents` rows = **0**; `search("energy")` → **0 results**.
- Drain the outbox → `search_documents` rows = 2; `search("energy")` → **1 result** (the document).

So the search use case, permission filter, embedder, and serializer were all correct — only the projection was unpopulated. (Document body content is intentionally not indexed — the index covers title + metadata; a body-only word like "solar" correctly returns 0. That is by design, not the bug.)

## 2. Fix (smallest correct — `search.py`, +13 lines)

**Read-time repair:** `GET /search` drains pending outbox events via the existing `SearchIndexApplier` *before* querying, so the derived projection reflects all committed writes.

- **Idempotent + bounded:** events are marked `delivered`; once caught up, each search's drain is a no-op. Verified empirically: undelivered count `2 → 0` after the first drain; stays `0` on subsequent drains (no re-processing, no re-embedding).
- **Best-effort:** `try/except` + `db.rollback()` — a drain failure never breaks search.
- **Reuse-only:** the existing `SearchIndexApplier` + outbox relay + the same embedder/vector the semantic leg already uses. No new search system, embedding abstraction, vector repo, provider, transport owner, or AI Core.

## 3. Per-layer verification

| Check | Result |
|---|---|
| 1. Backend `/search` directly (no frontend) | ✅ returns the document |
| 2. Lexical search (semantic disabled) | ✅ works (HashingEmbedder/None vector) |
| 3. Semantic search (flag on) | ✅ preserved (applier also upserts vectors) |
| 4. Qdrant availability | ✅ unavailable → `_safe_vector` catches; lexical drain proceeds (the route's try/except also protects) |
| 5. Embedder output | ✅ reused unchanged |
| 6. Vector collection dims | ✅ unchanged (same embedder identity) |
| 7. Permission filtering | ✅ unchanged — `SearchObjectsUseCase` R4 gate intact; restricted objects never returned |
| 8. Count before permission filter | ✅ projection populated by repair |
| 9. Count after permission filter | ✅ only readable objects returned |
| 10. Final `/search` JSON | ✅ `{"results":[…]}` — shape unchanged |
| 11. Frontend parsing | ✅ unchanged (M14 already fixed rendering) |
| 12. `SearchPage` render | ✅ results render |

## 4. Independent audit of the fix

| # | Check | Result |
|---|---|---|
| 1 | Root cause actually fixed? | ✅ document now found via `GET /search` with no manual sync |
| 2 | Search results work? | ✅ integration tests |
| 3 | Permissions preserved? | ✅ unchanged R4 gate; restricted-object tests still pass |
| 4 | Semantic search preserved? | ✅ |
| 5 | Lexical search preserved? | ✅ |
| 6 | Qdrant failure safe? | ✅ caught |
| 7 | Embedder failure safe? | ✅ caught |
| 8 | M11/M12 preserved? | ✅ architecture 16/16 |
| 9 | Architecture boundaries? | ✅ reuses `SearchIndexApplier`; no new infra |
| 10 | Duplicate infrastructure? | ✅ none |
| 11 | Read-repair efficient? | ✅ no-op once drained (verified) |
| 12 | No debug/secrets/dead code? | ✅ |
| 13 | Missing tests? | ✅ defect repro + contract covered |

**Findings:** Production-critical: **0**. Non-critical: **0**. (Note: document **body** content is intentionally not in the lexical index by design — title + metadata only. That is a documented limitation, not a defect; the reported symptom was the empty projection, now fixed.)

## 5. Test execution (actual)

| Suite | Result |
|---|---|
| Backend full suite | **1543 passed, 2 skipped, 0 failed** (1538 → 1543; +5) |
| Architecture guardrails | **16/16** |
| Search-targeted (api + read-repair + semantic) | passed |
| Frontend Vitest | **76 passed** (backend-only — unaffected) |
| TypeScript `tsc --noEmit` | **exit 0** |
| Ruff (changed files) | clean (only accepted `B008`/`E402`) |

One pre-existing test (`test_search_api.py::test_update_reflects_new_version_*`) encoded the old "stale until sync" assumption — the behaviour that **caused** the reported bug. It was **replaced** with a test proving the correct read-repair contract (search reflects committed writes immediately), per the spec's instruction to replace tests that encode incorrect behaviour.

## 6. Repository integrity
- Changed: `search.py` (+13), `test_search_api.py` (updated test), `test_search_read_repair.py` (new). Backend-only — no frontend, no architecture, no migration changes.
- No debug code, no secrets, no dead code, no new files beyond the test.
- Working tree clean after commit; branch `feature/m11-ai-workspace`.

## 7. Deliverables
- **Patch ZIP:** `releases/m14.1/m14.1-patch.zip`
- **Patch diff:** `releases/m14.1/m14.1.patch` (parent `2561cb8` → `aeaaa8f`)
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M14.1 entry prepended)
