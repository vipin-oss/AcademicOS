# Semantic Search Collection Policy (Sprint-5 M2)

Status: **live** · Owner: backend/search · Revision 1 (2026-08-06)

## 1. Purpose

The semantic leg of Global Search (Sprint-5 M2) stores one deterministic
`VectorDocument` per object in a Qdrant collection. This policy fixes the
collection schema, naming, versioning and operational procedures so the
index stays reproducible, swappable and never authoritative.

## 2. Reference

- AI Architecture doc A3.3 (vector store configuration) and A2.5 (dual-index
  alias swap for re-embedding).
- AI Architecture doc A4.1: the current embedder is the deterministic T0
  tier (hashing trick, 256 dims, in-process, no model, no network).
- Roadmap design gate 17: collections + embedding versioning.

## 3. Schema (one collection, one role)

| Aspect | Value | Rationale |
|---|---|---|
| Distance | `COSINE` | Document/query embeddings; matches the reference implementation |
| Dimensions | `256` | The T0 embedder's dimensionality (must equal the embedder's `dimensions`) |
| HNSW | `m=32`, `ef_construct=256` | A3.3 table |
| `ef_search` | 128 recommended at query time in production | Not passed per-request by the adapter for local-emulator parity; the real server accepts `SearchParams(ef_search=128)` |
| Point id | `uuid5(NAMESPACE_URL, object_id)` | Deterministic; required by the local emulator (CI), accepted by the server |
| Payload | `object_id`, `object_type`, `title`, `metadata_text`, `version`, `vector_role="doc"` | `object_id`/`version` are the identity + version guard; `vector_role` reserves the A3.2 multi-role scheme |
| Filtering | None in the vector store | Object-level ACLs are dynamic and evaluated through the R4 gate in the use case — never encoded as payload filters (tenancy/scoped payload filters arrive with the tenancy milestone) |

## 4. Naming and versioning (design gate 17)

- Base collections are immutable and versioned: `search_objects_v{n}`.
- All reads and writes go through the stable alias `search_objects_active`.
- **Re-embedding procedure** (embedder model change): build
  `search_objects_v{n+1}` from version snapshots via `rebuild()`, verify
  recall on the golden set, then atomically re-point the alias
  (`update_collection_aliases`); keep the old base collection for 7 days
  (A2.5).

## 5. Consistency doctrine

- The semantic index is **derived**; objects and version snapshots are
  authoritative. The lexical `search_documents` index is authoritative
  between the two projections: a vector-store failure is logged and
  isolated, never breaking the relay drain or search results (graceful
  degradation to lexical).
- The relay is the only indexing trigger; rebuild derives from version
  snapshots. Both paths share the same per-object derivation, so
  `rebuild == replay` is guaranteed and tested.
- Version guard: a stale `VectorDocument` (older `version`) never
  overwrites a newer stored projection (enforced by both the reference
  implementation and the Qdrant adapter).

## 6. Verification

- CI runs the Qdrant adapter against the in-process local emulator
  (`QdrantClient(":memory:")`) — the same code path as production.
- The reference implementation (`FakeVectorRepository`) mirrors the
  adapter's contract one-to-one; both are covered by the same-shaped test
  suites.
- Perf smoke (Sprint-5 M2): see `app/tests/unit/test_search_perf_smoke.py`
  for methodology and recorded p95 numbers. SRS §10.7 targets are R3
  steady-state (50B artefacts / 10k tenants) and cannot be reproduced in
  CI; the smoke indexes 5,000 documents and extrapolates.

## 7. Recorded numbers (2026-08-06, CI sandbox)

| Scenario (5,000 documents, 25 queries, warm) | p95 |
|---|---|
| Lexical (`text` LIKE over title + metadata) | **0.9 ms** |
| Hybrid (lexical + embedding + vector search + RRF fusion, full use case incl. R4 gate) | **212.6 ms** |

The hybrid p95 is dominated by the *reference implementation's* pure-Python
cosine scan over 5,000 vectors — a CI-only cost. The production Qdrant leg
answers the same query with an HNSW index server-side (sub-ms at this
scale; A3.3 targets recall ≥ 0.95 @ p99 < 40 ms at 10M vectors). The smoke
asserts generous order-of-magnitude bounds to catch regressions, never
micro-benchmarks.
