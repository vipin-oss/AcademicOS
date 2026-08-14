# ADR-044 — L8 evaluation gate (L8)

**Status:** ratified at L8. Activates an L8 evaluation gate for the cross-domain
completion layer (ADR-043) and records the minimal `gate_level="l8"` amendment to
the frozen L0 capability-evaluation schema.

## Context

L4/L5/L6/L7 each hard-gate their level via the frozen L0 capability framework
(ADR-038/040/042). L8 requires the same: a focused evaluation gate that verifies
real cross-domain completion behavior (multi-hop, absence, temporal, compare),
plus architecture guardrails. The L0 eval schema allowed `gate_level ∈ {l0_data,
l4, l5, l7, l9}`; to gate L8 golden cases at `l8`, the allowed set is extended
additively (the exact precedent of ADR-042 for `l7`).

## Decision

L8 adds:

- **`test_l8_eval_gate.py`** — verifies real behavior (≥15 cases): basic
  cross-domain completion; multi-hop via `sub_plans`; bounded multi-hop depth;
  ACL isolation across hops; absence with positive result; absence with
  insufficient-evidence result; temporal resolution; temporal
  filtering/completion; compare; deterministic ordering; evidence/citation
  preservation; memory-not-evidence; permission denial/no leakage; malformed/
  invalid sub-plan rejection; bounded execution/no uncontrolled recursion.
- **`test_l8_guardrails.py`** — pins: no new capability IDs; no L4 planner
  rewrite; no L5 executor rewrite; no ACL bypass; no L6 evidence bypass; no L7
  memory-as-evidence; bounded multi-hop; deterministic results; no new migration;
  no L9 implementation; no duplicate planner/retrieval/tool/evidence/memory
  subsystem.

## L0 framework amendment (minimal, additive)

`gate_level ∈ {l0_data, l4, l5, l7, l9}` → `{l0_data, l4, l5, l7, l8, l9}` in:

- `backend/app/application/capabilities/eval_schema.py` (`ALLOWED_GATE_LEVELS`)
- `backend/app/tests/eval/capabilities/test_golden_schema.py` (assertion set)

This is an additive change (adds one legal value), not a redesign. The frozen
capability registry (18 capabilities) and `test_l0_freeze_artifacts.py` are
unchanged — no new capability ID. Existing golden cases (l4/l5/l7) are not
weakened, skipped, or rewritten. The L8 gate tests real behavior, not class
presence, and uses the existing eval/golden conventions (no second eval
framework).

## Consequences

L8 cross-domain behavior is verified at the capability level, consistent with the
anti-patch and capability-evaluation doctrine. L15 consumes the same L8 contract.
