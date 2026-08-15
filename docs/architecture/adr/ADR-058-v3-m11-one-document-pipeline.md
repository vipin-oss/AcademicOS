# ADR-058 — V3 M11: one document pipeline (revisions + quarantine)

- **Status:** Accepted
- **Level:** V3 M11 (One Document Pipeline)
- **Supersedes:** nothing
- **Related:** ADR-021 (version supersession), M2 (dead `/documents/ingest` removal), M5 (typed claims), M10 (durable jobs), blueprint A9

## Context

R1 has two live entry points with subtly different failure semantics: the
direct upload (`documents.py`, which indexes content inline and swallows
extraction errors) and the folder import (`intake.py`, which drains through a
worker pool). Blueprint M11 makes them one predictable path: auth → stream →
hash → size/type check → quarantine → revision + job row, with immutable
revisions upgrading M5's `source_version` binding.

## Decision

1. **Canonical sync pipeline.** `DocumentPipeline` (application service)
   centralizes the sync upload contract every entry point routes through:
   size cap, sha256 content hash, a deterministic quarantine decision, and
   revision minting. Deterministic-only (no AI, no network).
2. **Immutable revisions.** A `document_revisions` table (migration 0019)
   records one row per upload (`document_id + revision_version +
   content_hash`). A new upload mints a NEW revision, never overwriting
   history — the explicit-revisions upgrade of M5's `source_version` binding
   (A9). `SQLDocumentRevisionStore.next_version` keeps versions monotonic.
3. **Quarantine.** Dangerous/known-malicious inputs (executable extensions,
   PE/ELF/shebang magic bytes, executable MIME) are flagged; they are STORED
   but never indexed/claimed — honesty over silent dropping, safety over
   execution. The direct upload skips content indexing for quarantined blobs.
4. **Async leg rides M10.** Extraction/embedding beyond the sync contract is
   M10's durable-job concern; this service owns only the sync sequence. The
   intake worker pool remains the folder-import processor.

## Consequences

**Positive**
- Uploads are processed identically regardless of entry point (hash, size,
  quarantine, revision).
- Revisions make version identity explicit and immutable (A9).
- Malicious files can never be executed; they are quarantined, not dropped.

**Negative / deferred**
- Full entry-point unification (making `intake.py` and `documents.py` literal
  thin adapters over ONE service) is an ongoing refactor; this ADR ships the
  shared pipeline contract both routes through, without rewriting the frozen
  intake worker semantics (anti-patch).
- Revisions are recorded on upload; the claim/CDM supersession cascade on a
  NEW revision (ADR-021) is wired when re-extraction lands on the revision
  identity — additive, not a rewrite.

**Revisit when:** the intake commit engine is migrated to mint revisions on
commit (replacing its implicit version bump) — then the two entry points are
truly one pipeline end-to-end.
