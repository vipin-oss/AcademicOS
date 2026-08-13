# AcademicOS — Knowledge Projection P0 — Change Report

**ZIP:** `AcademicOS_Knowledge_Projection_P0.zip`
**Date:** 2026-08-12
**Baseline:** GitHub `feature/m11-ai-workspace` @ `e323102` + ZIP-1 + ZIP-2 + AI Foundation P0 + Evidence Architecture P0 (verified by fresh clone + all five ZIPs, 77 focused tests green before implementation).
**Authority:** the FINAL RED-TEAM AUDIT (corrected P0). None of the six rejected designs were reintroduced (no CSV, no second pipeline, no file-replace endpoint, no version-as-change-authority, no ambiguous chunking, no unhandled delete race).

---

## 1. What was implemented

The persistent knowledge projection: a derived, rebuildable `document_chunks` segmentation of already-extracted content, with `content_hash` as the content-change authority, created by the SINGLE existing index consumer (`SearchIndexApplier`), repaired by an extended rebuild that now covers direct uploads, and protected against delete resurrection and the direct-upload crash window.

## 2. Files added (new)

| File | Purpose |
|---|---|
| `backend/app/application/services/document_chunking.py` | The ONE deterministic chunking algorithm: normalization (CRLF→LF, newline runs→paragraph, whitespace runs→single space, two-pass edge trimming); boundary priority paragraph→sentence→whitespace→hard split; sentence-aligned overlap; no-gap/no-mid-word invariants; `content_hash` (sha256 of normalized text). |
| `backend/app/application/ports/document_chunk_store.py` | Port: `replace` (per-document delete-then-insert, caller's tx), `delete_by_document`, `delete_all`, `count`, `by_document`. |
| `backend/app/infrastructure/persistence/document_chunk_store.py` | SQL implementation (dialect-agnostic, mirrors the content store). |
| `backend/app/infrastructure/db/models/document_chunk_model.py` | ORM: PK (document_id, chunk_index); content, span, token_count, content_hash, version, source_item_id, created_at. |
| `backend/alembic/versions/0010_document_chunks.py` | Migration: chunk table (FK→objects ON DELETE CASCADE, CHECK char_end > char_start, content_hash index) + `document_contents.content_hash` column. |
| `backend/app/tests/unit/test_document_chunking.py` | 16 tests incl. golden spans + invariants + determinism. |
| `backend/app/tests/unit/test_document_chunk_lifecycle.py` | 10 lifecycle tests (create/update/delete/idempotency/crash-window/delete-race). |
| `backend/app/tests/integration/test_document_chunks_rebuild.py` | 5 rebuild tests incl. the formal equivalence invariant. |

## 3. Files modified (complete replacement files)

| File | Change |
|---|---|
| `application/ports/document_content_store.py` | + `get_content_projection`, `set_content_hash`; `upsert(..., content_hash=None)`. |
| `infrastructure/persistence/document_content_store.py` | Implementations + hash column handling. |
| `infrastructure/db/models/document_content_model.py` | + `content_hash` (nullable; backfilled by rebuild). |
| `infrastructure/search/index_applier.py` | **The single chunk writer**: `_sync_chunks` on every document event (hash-guarded skip for metadata-only updates; skip cleanly when the content row is absent — crash window; backfills hash); chunk delete in the delete branch (deleted objects can never be resurrected — every event re-derives the aggregate); `chunk_store` param (defaults to SQL store); `stats` attribute (kept off the `apply_pending` return dict so existing `== {"applied": n}` contracts hold). |
| `infrastructure/search/document_content_rebuilder.py` | **Direct-upload rebuild gap fixed**: documents without an intake item resolve their stored blob (`file_path` metadata) → parse with the existing parser registry → text. Rebuild now recreates content rows (with content_hash) AND chunks in one transaction; returns `{indexed, skipped, chunked}`. |
| `api/routes/documents.py` | Direct-upload content write now stores `content_hash`. |
| `api/routes/search.py` | `ContentRebuildResponseModel` + `chunked` counter. |
| `application/use_cases/intake/commit_item.py` | Intake-commit content write stores `content_hash`. |
| `scripts/init_db.py` | Registers the chunk model; stamps `0010_document_chunks`. |
| `tests/unit/test_document_content_commit.py` | `RecordingContentStore` implements the extended port. |

## 4. Architectural decisions (per the red-team audit)

1. **One chunk writer** — only `SearchIndexApplier`; no parallel pipeline.
2. **`content_hash` (normalized text sha256) is the change authority**; object `version` only guards optimistic writes (PK (document_id, chunk_index) already forbids two versions coexisting).
3. **Chunking is ONE deterministic algorithm** with golden fixtures; rebuild reproduces it exactly.
4. **ACL is never copied into chunks** — chunks carry `document_id` only; every leg resolves the object and applies the R4 gate at query time.
5. **Crash window** (direct upload: outbox event before content commit) → applier skips (no empty evidence); rebuild repairs from the stored blob.
6. **Delete race** → applier delete branch removes content+chunks; `SearchObjectsUseCase` drops any orphaned projection via the object-existence check (tested).
7. **Rebuild equivalence** is a formal invariant, tested per object on (content_hash, ordered chunk signature) — not row counts.

## 5. Validation results

| Suite | Result |
|---|---|
| Focused (chunking 16 + lifecycle 10 + rebuild 5) | **31 passed** |
| Retrieval/AI/evidence regression (12 suites) | **199 passed** |
| **Full backend** | **1,816 passed, 2 skipped** (baseline 1,785 + 31 new) |
| Frontend | 101 passed (unchanged) |
| TypeScript typecheck | 0 errors |
| `git diff --check` | clean |
| `init_db.py` | creates `document_chunks` + `content_hash`, stamps 0010 |

**Pre-existing failures (classified):** 9 × `test_qdrant_vector_repository.py` — environment dependency (no Qdrant server in the sandbox); identical on the pristine baseline; unrelated to this patch.

## 6. Real-data E2E validation (mini corpus, measured)

| Stage | Result | Measured |
|---|---|---|
| Direct upload (long PDF) | content + chunks created via route → drain | 78.8 ms (incl. extraction + content write) |
| Direct upload (short/medium) | 1 chunk each | 4.0–4.7 ms |
| Intake (folder import) commit | chunks created, `source_item_id` = item | — |
| Rejected/failed item | **0 chunks, never evidence** | — |
| Duplicate content upload | independent object + chunks | 7.3 ms |
| Drain (5 docs + 10 non-doc events) | `chunk_created=5, chunk_skipped=10` | 34.9 ms |
| Retrieval (exact doc-ref query) | target document retrieved, plan `document_ref` | 4.4 ms |
| Target chunk content | contains the conference name; span hash OK | — |
| Metadata-only update | **0 re-chunks** (hash-guard) | — |
| Delete | chunks + content removed; no resurrection | — |
| Rebuild (4 docs) | `{indexed:4, skipped:0, chunked:4}` | 13.8 ms |
| **Rebuild equivalence** | incremental == rebuilt (per-object chunk signatures) | **True** |
| Rebuild repair of crash window | content + chunks reconstructed from blob | — |

## 7. Known limitations (deliberate P1/P2, not defects)

- Chunks are written at indexing time; **chunk-scoped retrieval/evidence assembly** (querying chunks directly) is P1 — P0 only makes the projection exist, with zero query-time cost.
- FTS/tsvector over chunks is P1 (existing LIKE remains correct at this scale).
- Chunk embeddings / vector lifecycle is P2 (Qdrant still embeds title+metadata only).
- No file-replacement endpoint (out of scope by instruction); the hash-driven lifecycle is designed so a future endpoint needs no redesign.
- `POST /search/content/rebuild` is the backfill/repair path for pre-existing documents (run once after applying, per APPLY_STEPS §9).

## 8. Final architectural invariants (all satisfied)

1. Objects/object_versions/blobs/ACL remain the only source of truth.
2. Chunks are disposable, rebuildable, derived projections.
3. Original files are not parsed for ordinary queries (extraction happens once; chunks are written once).
4. Every chunk carries provenance (document_id, version, span, content_hash, source_item_id).
5. Every retrieval result is ACL-checked at query time (chunks never an authorization layer).
6. Deleted/rejected objects cannot remain usable AI evidence.
7. Indexing is idempotent (hash-guarded; delete-then-insert).
8. Rebuild produces equivalent projections (tested formally).
9. All five product areas share the same knowledge architecture (chunks only for documents; structured objects keep metadata_text evidence).
10. No query-specific hacks; no second AI database; semantic retrieval remains optional.
