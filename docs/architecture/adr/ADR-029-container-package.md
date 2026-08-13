# ADR-029 — Container / package handling (L2)

**Status:** ratified at L2. Implements the package/container contract from
ADR-023 (source identity) with safe expansion and member provenance.

## Decision

A ZIP/package is a **container Source** (`MediaKind.PACKAGE`). A safe expander
(infrastructure, stdlib `zipfile`) expands it into member blobs; each supported
member becomes an **independent Source** carrying `container_source_id` +
`container_path` (package provenance). Member version/source binding follows the
L1 version-identity rule (ADR-027).

## Safety boundaries (enforced)

- **Path traversal:** reject absolute paths, `..`, and symlinks.
- **Decompression/resource exhaustion:** total-uncompressed cap, member-count
  cap, per-member cap, compression-ratio cap.
- **Nesting:** bounded depth; nested members carry the container chain.
- **Duplicates:** deterministic (first-wins + warning), never silent.
- **Corrupt / unsupported members:** explicitly represented as member-level
  status — **never silently dropped**.
- **Member isolation:** one bad member does not corrupt siblings.

## Rules

1. A container member is independently identifiable and versionable.
2. Unsupported/corrupt members are reported (member status), not dropped.
3. No member silently disappears from provenance.

## Consequences

ZIP ingestion preserves package identity and member provenance end-to-end, with
explicit isolation and bounded resource use.
