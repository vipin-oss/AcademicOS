# ADR-054 — V3 M7: review at scale + extraction-health correction loop

- **Status:** Accepted
- **Level:** V3 M7 (Review at Scale + Correction Loop)
- **Supersedes:** nothing
- **Related:** ADR-032 (decision audit), ADR-033 (triage), ADR-053 (Wave 1 catalogue), audit A10 (AUTO_SUGGESTED), blueprint §B6 (gates)

## Context

M6 made the system read two document types and propose (or AUTO_SUGGEST)
claims. M7 makes the resulting review backlog manageable and turns every
human correction into a durable improvement signal, without breaking the
authority boundary: only human confirmation creates institutional truth
(A10 / ADR-006).

## Decision

1. **Bulk confirmation (never auto-approval).** `BulkConfirmationService`
   confirms every AUTO_SUGGESTED claim at/above a 0.95 confidence floor in one
   caller-owned transaction. Every claim is confirmed through the existing
   `ClaimConfirmationService.approve`, so each confirmation is a separate,
   durable, human-attributed decision row (ADR-032) — the bulk action is
   auditable, atomic (a failure rolls the batch back), and undoable through
   the existing reject/correct endpoints. ACL-gated: a claim the reviewer may
   not decide on is skipped, never confirmed.
2. **Extraction-health aggregation.** `ExtractionHealthService` aggregates the
   `correct` decision trail into per-predicate correction counts + a recent
   trend. The most-corrected predicates are where the extractor keeps failing
   — the signal for template/predicate fixes, which are data edits (ADR-053),
   not deploys.
3. **Conflict escalation.** `ConflictReport` surfaces, side-by-side, a
   non-authoritative candidate (PROPOSED / AUTO_SUGGESTED) whose value differs
   from an existing CONFIRMED claim of the same predicate. Conflicts are
   escalated, never silently resolved.

## Consequences

**Positive**
- Review is bulk-capable without sacrificing attributability or atomicity.
- The correction loop is closed: fixes aggregate into a health signal that
  drives template/predicate (data) fixes.
- Conflicts can no longer be silently merged into authoritative truth.

**Negative / deferred**
- The column-mode review UI (group by field, keyboard-only) is a frontend
  surface; this ADR ships the backend contract (bulk-confirm + health +
  conflicts) the UI will consume. The existing per-item endpoints remain the
  atomic fallback.
- `recent_corrections` loads recent decisions and resolves each to its
  predicate via the claim store; bounded by `limit`, acceptable for a
  health screen (not a hot read path).

**Revisit when:** the review UI is built (M14 multi-user UX); the health
aggregation may then move behind a materialized counter if it becomes a hot
path at scale (SCALE_LAW).
