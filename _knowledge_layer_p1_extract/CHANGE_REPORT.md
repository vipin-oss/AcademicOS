# AcademicOS — P1 Knowledge-Layer Scale & Identity — Change Report

**ZIP:** `AcademicOS_KnowledgeLayer_Scale_Identity_P1.zip`
**Date:** 2026-08-12
**Baseline:** **`e14aa6b`** (`Fix graph neighbor citation leakage`) on `feature/ai-knowledge-projection-p0` — verified by fresh clone.
**Scope:** ONE coherent P1 — full-text search, bounded content retrieval, document identity/dedup. No classification, no entities, no web, no external GPT, no embeddings, no ES, no tenancy (explicitly deferred to P2/P3). Nothing committed or pushed.

---

## A. Root cause / current scale limitation (verified on e14aa6b)

1. **No FTS** — `infrastructure/search/` contains only `index_applier.py` + `document_content_rebuilder.py`; retrieval is `LIKE %term%`.
2. **Unbounded content-leg merge** — the `content_hits` fetch in `sqlalchemy_search_repository.py` had no LIMIT; a common term loaded every matching document row.
3. **No document identity** — `content_hash` (sha256 of normalized extracted text) was written by both content writers but never used for duplicate detection.
**Measured on the baseline branch:** 1k docs → 6.5 ms returning all 1,000 rows; 6k docs → 26.1 ms returning all 6,000 rows.

## B. Exact architecture implemented

```
objects + blobs + ACL (authoritative, unchanged)
   └─ SearchIndexApplier (THE single projection writer)
        ├─ search_documents      (unchanged)
        ├─ document_contents    (+ content_hash index)
        ├─ document_chunks      (unchanged)
        ├─ document_search_fts  (NEW: PG tsvector+GIN / SQLite FTS5,
        │                        title+metadata+content+chunks; derived)
        └─ document_registry    (NEW: content_hash PK, canonical =
                                 smallest object_id, count; derived)
   └─ SearchObjectsUseCase → SQLAlchemySearchRepository
        ├─ FTS-first (bounded, ranked, exclude_types in query;
        │            authoritative miss; LIKE fallback when FTS absent)
        └─ bounded legacy content leg (_CONTENT_LEG_CAP=200 at the SQL
                                     boundary; deterministic merge cap)
```

**Identity semantics:** identity = `content_hash` (normalized-text sha256) — never filename, never version. Canonical representative = smallest `object_id` among same-hash documents (deterministic, rebuildable, survives deletion of the canonical via recompute). Duplicates are **detected, never merged**: every document keeps its own object/chunks/citations.

## C. Exact files changed (15)

**Modified (6):** `api/routes/search.py` (+`duplicates` in rebuild response), `infrastructure/db/models/document_content_model.py` (content_hash index), `infrastructure/repositories/sqlalchemy_search_repository.py` (FTS-first + bounded legs), `infrastructure/search/document_content_rebuilder.py` (FTS + registry rebuild in one transaction), `infrastructure/search/index_applier.py` (`_sync_fts`, `_sync_identity`, `_remove_identity`, `_safe_fts`/`_safe_identity`, stats, delete branches), `scripts/init_db.py` (identity model, `ensure_fts_schema`, stamp 0011).

**New (9):** `infrastructure/search/fts.py` (dialect-aware FTS + `SQLFTSRepository`), `application/ports/document_identity_store.py`, `infrastructure/db/models/document_identity_model.py`, `infrastructure/persistence/document_identity_store.py`, `alembic/versions/0011_search_fts_identity.py`, `tests/unit/test_fts_search.py`, `tests/unit/test_document_identity.py`, `tests/integration/test_scale_identity_rebuild.py`, `scripts/benchmark_p1.py`.

**Not changed:** intake pipeline, queue, auth, UI, ACL evaluator, graph runtime, evidence assembly, claim verifier, chunking algorithm, document-reference resolution.

## D. Tests and measured results

| Suite | Result |
|---|---|
| New P1 tests (FTS 12, identity 8, scale/rebuild integration 5) | **25 passed** |
| Evidence + graph-filter + chunk + retrieval regression (16 suites) | **214 passed** |
| **Full backend** | **1,855 passed, 2 skipped** (only 9 pre-existing Qdrant env failures; flaky intake test passed this run) |
| Frontend / typecheck | 101 passed / 0 errors |
| `git diff --check` | clean |

## E. Benchmark table (SQLite, this environment — PG not claimed from SQLite)

| Docs | Realistic (~20% match) | Candidates | Pathological (100% match) | Chunk+assembly | Duplicate check |
|---|---|---|---|---|---|
| 100 | 3.3 ms | 8 | 1.4 ms | 1.33 ms | 1.34 ms |
| 1,100 | 2.9 ms | 8 | 5.3 ms | 0.55 ms | 0.36 ms |
| 11,100 | **7.3 ms** | **8** | 21.5 ms | 0.45 ms | 0.31 ms |

**Acceptance: PASS** — realistic 10k retrieval 7.3 ms (<20 ms), candidates bounded at 8 (was: all matching rows). Pathological 100%-match = 21.5 ms, reported separately (FTS5 bm25 must visit every matching row for global ranking; PG `ts_rank` has the same property — a documented P2 bounded-pool option). Before P1: 6k docs → 26.1 ms returning all 6,000 rows.

## F. Duplicate/identity behavior (verified)

- New doc → its own canonical. Duplicate content (different filename) → detected, canonical = smallest object_id, `duplicates` count = 1, both docs independently retrievable (no merge). Same filename + different content → different identity (never merged by filename). Version changes → identity unchanged. Delete canonical → next representative becomes canonical (deterministic recompute). Rebuild → identical registry (incremental == rebuilt).

## G. Rebuild/lifecycle result

`rebuild_document_contents` + `SearchIndexApplier.rebuild` + re-drain produce **equivalent FTS rows and registry** (tested: wipe ALL derived projections → rebuild → same FTS ids for the same terms, same canonical). Deleted documents never reappear through FTS/content leg (stale-event safe, tested). Chunk lifecycle untouched (spans deterministic, tested).

## H. CBLU + graph-citation regression

- `test_claim_support.py` 26, `test_evidence_contract.py` 16, `test_chunk_evidence_path.py` 7 (CBLU supported/unsupported through the chunk path), `test_graph_citation_filter.py` 7 (certificate-only citation, event metadata suppressed) — **all green, unchanged behavior**.

## I–L. Deliverable

- ZIP: `AcademicOS_KnowledgeLayer_Scale_Identity_P1.zip` (SHA-256 recorded at delivery).
- Manifest: 6 modified + 5 new production + 3 new test + 1 benchmark + 3 docs = 18 entries, repo-relative only.
- Fresh-clone validation: applied to a fresh `e14aa6b` clone; new P1 tests + regressions re-run green; benchmark re-run; CBLU/graph-citation verified.

## M. Known limitations

1. PG path (tsvector/GIN) is code-complete and migration-tested for schema, but not runtime-benchmarked here (no PG server in sandbox) — benchmark on your PG before trusting 10k numbers there.
2. Pathological 100%-match queries remain >20 ms at 10k (21.5 ms measured) — documented; bounded-pool ranking is a P2 option.
3. Duplicate detection is currently surfaced via the registry (queryable, rebuild stats); a user-facing "duplicate detected" notice in the upload UI is P2.
4. FTS uses the deterministic `simple` config (no stemming).
