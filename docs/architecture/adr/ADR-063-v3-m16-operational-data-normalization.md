# ADR-063 — V3 M16: operational data normalization (wave framework + wave 1)

- **Status:** Accepted
- **Level:** V3 M16 (Operational Data Normalization)
- **Supersedes:** nothing
- **Related:** SCALE_LAW, M3 (tenant stamping), blueprint §M16

## Context

Operational data (users, enrollment, attendance, supervision, research,
finance) lives as `UniversalObject` + metadata JSON; hot reads do full-table
`repository.find()`/`list()` scans. The blueprint wants these normalized into
typed tables, one reversible WAVE at a time, with `UniversalObject` retreating
to its correct role — the identity/graph anchor, never the query surface.

## Decision

1. **A frozen 5-phase wave doctrine.** Every wave runs `EXPAND → BACKFILL →
   VALIDATE → SWITCH READS → SWITCH WRITES` through a `NormalizationRunner`
   that HALTS (and rolls back) on VALIDATE failure — a half-migrated
   projection can never serve reads.
2. **Projections are derived and reversible.** Each wave adds a typed,
   indexed table backfilled idempotently from the authoritative objects; the
   object stays the source of truth (SWITCH WRITES keeps it), the projection
   is rebuildable and dropped on rollback (reads fall back to the object
   store on a miss).
3. **Wave 1 — user_state.** `user_profiles` (migration 0023) projects the
   user object's hot fields (username / display name / roles / institution).
   This is the demonstrated first wave; the remaining waves (enrollment,
   attendance/assessment, supervision, research/authorship, finance) are the
   SAME mechanism applied incrementally — additive, never a rewrite of the
   frozen modules.

## Consequences

**Positive**
- A reusable, reversible, validated normalization mechanism — no ad-hoc
  migrations, no half-migrated reads.
- The first hot read (user listing) no longer needs a full object scan.
- `UniversalObject` is preserved as the identity/graph anchor.

**Negative / deferred**
- Waves 2–6 (enrollment → finance) are enumerated, not yet implemented; each
  is an additive wave on this framework, independently reversible.
- The projection is updated on write via re-backfill (SWITCH WRITES is a
  no-op seam today); a per-write projection refresh is wired when a wave's
  writes are hot.

**Revisit when:** a measurement shows a specific operational module's
full-table scan is a hot-path cost — apply the next wave to that module.
