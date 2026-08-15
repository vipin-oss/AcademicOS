# ADR-021 — File-version → claim / CDM supersession (M-3)

**Status:** law recorded at L0. Cascade **code** is L1 (requires the
claim store and CDM). This ADR does not implement either.

## Decision

When a document is replaced by a newer file version:

1. Old CDM and old claims become **SUPERSEDED** (never silently deleted).
2. Re-extraction **proposes** new claims (`PROPOSED`). Nothing is
   silently promoted to current truth.
3. Nothing is **silently merged** with the previous version’s facts.
4. Historical / **as-of** queries use the supersede chain.

## Rules

- Supersede-not-delete.
- Duplicate re-uploads of identical normalized content remain
  content-identity links (ADR-002b), not a version replacement.
- An explicit new file version is what triggers this cascade.
- Citations to superseded claims are not current evidence.

## Consequences

A revised sanction letter cannot leave the old sanctioned amount
standing as if current. L2 PDF/OCR engines write proposals into this
lifecycle; they do not invent merge rules.
