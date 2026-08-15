# AcademicOS — Knowledge Projection P0 — Architecture Report

**Date:** 2026-08-12 · **Scope:** implementation record of the red-team-corrected P0.

---

## 1. Layered model (as implemented)

```
AcademicOS objects + object_versions + blobs + ACL        [AUTHORITATIVE]
        │  outbox relay (existing)
        ▼
SearchIndexApplier (existing, extended — THE single index consumer)
   ├─ search_documents     (metadata projection; unchanged)
   ├─ document_contents    (+ content_hash: sha256 of normalized text)
   ├─ document_chunks      (NEW: deterministic segmentation, PK (doc, idx))
   └─ vectors              (optional; unchanged, P2 chunk embeddings)
        │
        ▼
Retrieval (unchanged; ACL at query time) → Evidence (unchanged) → Claim verification (unchanged)
```

**What is authoritative:** objects, object_versions, blobs, ACL, relationships, outbox.
**What is derived & rebuildable:** extraction blob, search_documents, document_contents, document_chunks, vectors.
**What is indexed:** search_documents (title+metadata), document_contents (whole text), document_chunks (P0: written; P1: queried), vectors (title+metadata today).
**What is evidence:** the ACL-gated subset passed to generation (unchanged contract).
**What is provenance:** document_id, version, chunk_index, char_start..char_end, content_hash, source_item_id, file_name.

## 2. The chunking algorithm (one, deterministic)

- Normalization: CRLF/CR→LF; 3+ newlines→paragraph break; space/tab runs→single space; spaces around newlines stripped (two passes); ends trimmed.
- `chunk_text(text, max_chars=1000, overlap=120)`:
  - boundary priority in `[start, start+max_chars)`: paragraph (`\n\n`) → sentence (`.!?` + space/newline/end) → whitespace → hard split;
  - next start = `end - overlap`, advanced to the FIRST sentence boundary in the overlap tail (skip trailing whitespace); chunks ≤ overlap get no overlap; hard progress guard as a last resort;
  - invariants: no gaps (`next_start ≤ end`), no mid-word splits, absolute spans, byte-identical output for identical input (golden fixtures pin the exact spans).
- `content_hash(text)` = sha256(normalize(text)) — the change authority; distinct from source-file SHA-256 (intake `KEY_SHA256`), which remains a complementary fact.

## 3. Lifecycle (as implemented)

- CREATE: intake commit / direct upload write the content row (with content_hash) → outbox → applier `_sync_chunks`: content missing/empty → skip (crash window, no empty evidence); hash equal + chunks present → skip; else chunk_text → delete-then-insert per document in the batch transaction → backfill hash.
- UPDATE: metadata-only → search_documents refreshed, chunks untouched (hash guard). Content change → requires a future file-replace endpoint (out of scope); when it lands, the same hash-guard path replaces chunks — no redesign.
- DELETE: applier delete branch removes search_documents + document_contents + document_chunks (+ vectors); stale events cannot resurrect (every event re-derives the aggregate; re-derivation of a deleted object is None).
- REJECT: rejected intake items never become documents; no chunks.
- IDEMPOTENT: PK upserts + delete-then-insert + hash guard; running twice is stable (tested).

## 4. Rebuild (as implemented)

`rebuild_document_contents(session, storage)` — one transaction (delete-all content+chunks → re-upsert):
- intake origin: BELONGS_TO → intake item → descriptor `text_key` → blob (unchanged);
- **direct-upload origin (gap fixed):** `file_path` metadata → stored blob → `build_document_parsers()` → text;
- every row gets content_hash; every document gets chunks from the same deterministic chunker;
- returns `{indexed, skipped, chunked}`; missing/corrupt blobs → skipped, never fatal;
- **equivalence invariant (tested):** `IncrementalProjection(S) == RebuiltProjection(S)` per object on (content_hash, ordered chunk signature: index/span/content/hash/version).

## 5. ACL / security

Chunks store `document_id` only — no ACL copy. Every retrieval leg (SQL, content, chunks, vectors, graph, citations) resolves the object and applies the R4 gate at query time. Orphaned projections (crash window) are dropped by the object-existence check in `SearchObjectsUseCase` (tested). Tenant isolation (future) lives at the object scope; the index never bypasses it.

## 6. Failure recovery (as implemented)

Duplicate/out-of-order events → version-guarded upserts + re-derivation; crash during chunking → batch rollback + outbox redelivery; missing content projection → skip + rebuild repair; deleted object during indexing → idempotent delete; rebuild interruption → transactional, safe to re-run; vector failures → existing best-effort `_safe_vector`.

## 7. Scale posture

P0 adds write-time O(text) chunking once per document and zero query-time cost (chunks are written, not queried, until P1 chunk-scoped assembly). Measured in this environment: extraction+content ~4–80 ms/doc; drain (5 docs) ~35 ms; retrieval ~4.4 ms; rebuild (4 docs) ~14 ms. FTS/tsvector (P1) and chunk vectors (P2) extend this without redesign; Elasticsearch remains a Phase-3 measured decision.

## 8. Observability

`SearchIndexApplier.stats = {chunk_created, chunk_skipped, content_backfilled}` per drain (kept off the `apply_pending` return dict for backward compatibility); rebuild returns `{indexed, skipped, chunked}`; chunk rows carry full provenance for audit.
