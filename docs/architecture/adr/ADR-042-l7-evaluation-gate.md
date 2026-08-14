# ADR-042 — L7 evaluation gate (L7)

**Status:** ratified at L7. Activates an L7 evaluation gate for the persistent
memory layer (ADR-041) and records the minimal `gate_level="l7"` amendment to
the frozen L0 capability-evaluation schema.

## Context

L5 (ADR-038) and L6 (ADR-040) each hard-gate their level via the frozen L0
capability framework. L7 requires the same: a focused evaluation gate that
verifies real persistent-memory behavior, plus a golden capability set gated at
`l7`.

## Decision

L7 adds:

- **`test_l7_eval_gate.py`** — verifies real behavior: memory creation, recall,
  ACL isolation (no cross-principal leak), provenance preservation,
  supersession/consolidation, memory-not-evidence, deterministic ordering, and
  permission denial / no-leakage.
- **`test_l7_guardrails.py`** — pins that L7 reuses existing infrastructure and
  does not introduce a second memory store, retrieval system, ACL system,
  planner, tool registry, or evidence system; that L7 does not touch frozen
  L4/L5/L6 files; that memory is context-not-evidence; and that no L7 migration
  exists.

The L7 evaluation gate is **self-contained** (`test_l7_eval_gate.py` exercises
real persistent-memory behavior directly). L7 does **not** introduce a new
frozen capability ID and does **not** add a `memory.json` file to the frozen
capability suite. The L0 frozen capability registry therefore remains exactly
the frozen 18 capabilities (ADR-019+ / `test_l0_freeze_artifacts.py` unchanged).

## L0 framework amendment (minimal, additive)

The frozen L0 evaluation schema allowed `gate_level ∈ {l0_data, l4, l5, l9}`.
To hard-gate L7 golden cases at `l7`, the allowed set was extended additively
to `{l0_data, l4, l5, l7, l9}` in:

- `backend/app/application/capabilities/eval_schema.py` (`ALLOWED_GATE_LEVELS`)
- `backend/app/tests/eval/capabilities/test_golden_schema.py` (assertion set)

This is an **additive** change (adds one legal value), not a redesign of the
evaluation framework. No existing golden case, capability, or gate is weakened,
skipped, or rewritten.

## Rules

1. The frozen L0 evaluation framework is NOT redesigned; only the legal
   `gate_level` set gains `l7` additively.
2. Existing golden cases (l4/l5/l9) are not weakened, skipped, or rewritten.
3. The gate tests real behavior, not class presence.

## Consequences

L7 persistent-memory behavior is verified at the capability level, consistent
with the anti-patch and capability-evaluation doctrine. L8 consumes the same
memory contract.
