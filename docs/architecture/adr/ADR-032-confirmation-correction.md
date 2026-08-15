# ADR-032 — Confirmation & correction (L3)

**Status:** ratified at L3. Implements Freeze-Contract ADR-006 and Part 13.3.5
(human confirmation; corrections as data, never destructive).

## Decision

Human-in-the-loop confirmation/correction over the L1 claim/CDM plane:

- **Approve** a PROPOSED claim/block → CONFIRMED, `Provenance.ASSERTED`
  (immutable to machine writes, FR-MET-009).
- **Reject** → REJECTED, kept for audit, never auto-usable.
- **Correct** → a **new ASSERTED claim** (human value) is created and
  **supersedes** the candidate via `supersedes_claim_id` (ADR-021). Destructive
  edits to historical evidence are forbidden.
- Every action writes a **durable decision row** (reviewer, timestamp,
  previous_status, resulting status, notes, acl_scope) — idempotent by
  `decision_id`.

## Rules

1. Claim decisions are stored in a **claim-scoped** decision table, NOT the
   conversation-scoped `review_decisions` table (no incorrect coupling to
   assistant reviews).
2. Only CONFIRMED/ASSERTED claims are auto-usable (`Claim.is_authoritative`).
3. Confirmation actions enforce ACL: the reviewer needs WRITE/MANAGE on the
   source scope.
4. Rejections can be linked to an evaluation run (`eval_run_id`).
5. Corrections preserve the supersede chain; history is never deleted.

## Consequences

L3 makes every confirmation/correction auditable and attributable while keeping
candidate facts distinguishable from confirmed/canonical knowledge.
