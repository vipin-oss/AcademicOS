# ADR-064 — V3 M17: temporal graph + identity resolution

- **Status:** Accepted
- **Level:** V3 M17 (Temporal Graph & Identity Resolution)
- **Supersedes:** nothing
- **Related:** ADR-021 (version supersession), M11 (revisions), blueprint §M17

## Context

The blueprint wants validity intervals on relationships, transliteration-based
identity matching (Vipin ↔ विपिन), ORCID/DOI/institutional ID resolution, and
human-reviewed merge — with NO automatic irreversible merge. It also flags
that `claims` / `claim_spans` have no foreign keys, so deleting a document
orphans evidence.

## Decision

1. **Validity intervals.** `object_relationships` gains nullable
   `valid_from` / `valid_to` (ISO-8601) — absent = open interval.
2. **Evidence foreign keys (RESTRICT, never cascade).** `claims.
   source_document_id` and `claim_spans.source_id` gain `ON DELETE RESTRICT`
   FKs to `objects(id)`. Deleting a document that still has claims/spans is
   REFUSED — evidence is never cascaded away. PostgreSQL-only (SQLite runs
   with FK enforcement off); the production guarantee is the Postgres
   constraint.
3. **Deterministic transliteration.** A closed Devanagari↔Latin character map
   produces a canonical `match_key` so ``Vipin`` == ``विपिन`` — a matching aid,
   no model, no network.
4. **Identity resolution is read-only.** `IdentityResolutionService` proposes
   candidates (transliteration + declared identifier), never merges. Merge /
   split / redirect is a human decision recorded as data.

## Consequences

**Positive**
- Temporal "as-of" questions are representable on edges.
- Evidence can no longer be silently orphaned in production (Postgres).
- Cross-script identity matching without a model; merge stays human-controlled.

**Negative / deferred**
- The FKs are enforced only on PostgreSQL (SQLite dev/tests skip enforcement).
- Merge/split/redirect is surfaced, not yet wired to a full review UI; the
  service is the backend contract.
- The transliteration alphabet is closed and academic-name focused; new glyphs
  are additive map entries.

**Revisit when:** the identity review UI is built (M14 frontend work) — then
merge/split/redirect actions consume these candidates.
