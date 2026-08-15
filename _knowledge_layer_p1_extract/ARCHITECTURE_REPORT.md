# AcademicOS — P1 Knowledge-Layer Scale & Identity — Architecture Report

**Date:** 2026-08-12 · **Baseline:** e14aa6b (verified by fresh clone) · **Scope:** one coherent P1.

---

## 1. Layered model (as implemented)

```
AcademicOS objects + object_versions + blobs + ACL        [AUTHORITATIVE]
        │  outbox relay (existing)
        ▼
SearchIndexApplier (existing, extended — THE single index consumer)
   ├─ search_documents     (metadata projection; unchanged)
   ├─ document_contents    (+ content_hash index — identity signal)
   ├─ document_chunks      (deterministic segmentation; unchanged)
   ├─ document_search_fts  (NEW: tsvector+GIN on PG / FTS5 on SQLite,
   │                        derived from title+metadata+content+chunks)
   └─ document_registry    (NEW: content_hash → canonical document id
                            (smallest object_id) + document count)
        │
        ▼
SearchObjectsUseCase → SQLAlchemySearchRepository
   ├─ FTS-first query path (bounded top-N, ranked, exclude_types in the
   │   query; authoritative miss; LIKE fallback when FTS is unavailable)
   └─ bounded legacy content leg (_CONTENT_LEG_CAP=200 at the SQL
                                  boundary; deterministic merge cap)
        ▼
ACL gate (query time, unchanged) → graph leg (unchanged) → evidence assembly
→ claim verification (unchanged) → citations (search-hit evidence only)
```

## 2. Design decisions

1. **One projection lifecycle**: the applier is the only writer of FTS + registry; the rebuild path reproduces them in the same transaction (ownership-scoped `delete_many` — never wipes rows it does not own). No second indexing system.
2. **FTS is authoritative when available** (a miss returns no candidates — never an unbounded LIKE fallback); graceful degradation when the table is absent (pre-0011 DBs keep the LIKE path).
3. **Bounded at the SQL boundary**: the content-leg fetch has `LIMIT _CONTENT_LEG_CAP`; the merged candidate set is capped deterministically (title-exact first, then object_id). A common term can never load every document row.
4. **Identity = content_hash** (sha256 of the NORMALIZED extracted text): never filename, never version. Canonical = smallest object_id per hash — deterministic, rebuildable, stable across deletes (recompute). Duplicates are detected, never merged: each document retains its own object/chunks/citations/provenance.
5. **Cross-tab**: everything rides the shared UniversalObject + outbox + ACL foundation; the projections are per-object (documents AND structured objects get FTS rows; the registry concerns documents with content). No parallel document database.
6. **Preserved invariants**: ACL at query time (denied user blocked on the FTS path, tested); exclude_types in the query; deterministic ranking/tie-breaks; exact filename/title lookup; graph-only neighbors remain non-citable; chunk evidence + span provenance; claim verification + unsupported-claim refusal; rebuild equivalence; single source of truth; single projection writer.

## 3. Failure/recovery

Duplicate/out-of-order events → version-guarded idempotent upserts; missing FTS/registry tables → `_safe_fts`/`_safe_identity` degrade without breaking the drain; deleted objects → idempotent delete of all projections (re-derivation makes stale events harmless); interrupted rebuild → transactional delete-all + re-upsert, safe to re-run; registry canonical deletion → deterministic recompute from remaining content rows.

## 4. Scaling posture (measured, honest)

- SQLite measured: 10k realistic retrieval 7.3 ms, candidates bounded (8); pathological 100%-match 21.5 ms (reported separately).
- PostgreSQL: schema-ready (migration 0011); runtime numbers must be measured on your PG — SQLite numbers are NOT claimed as PG numbers.
- 100k: requires PG + partitioning + (optionally) chunk-level vectors (P2/P3) — explicitly not in P1.

## 5. What P1 deliberately does NOT include

Automatic document classification, entity resolution, web/Google search, external GPT context API, embeddings, LLM judge, Elasticsearch, tenancy, automatic folder movement — all later phases, none of which need a P1 redesign.
