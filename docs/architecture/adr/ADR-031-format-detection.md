# ADR-031 — Format detection (L2)

**Status:** ratified at L2.

## Decision

Engine selection is based on the **deterministic extension table** (existing
`SUPPORTED_FORMATS` / `format_of`) as the primary signal. A **format detector**
(infrastructure) cross-checks magic bytes / MIME against the claimed extension:

- match → proceed
- mismatch → recorded as a warning; the parser is NOT changed by content
  guessing (no AI/content-sniffing), and the mismatch is surfaced honestly
- unknown extension → `UNSUPPORTED` (existing convention), never a crash

## Rules

1. Content is never used to silently re-route to a different parser family.
2. MIME/content mismatch is recorded, not silently accepted.
3. `MediaKind` is derived deterministically (ADR-023), independent of parser.

## Consequences

Deterministic, honest format handling without reintroducing content-guessing
heuristics.
