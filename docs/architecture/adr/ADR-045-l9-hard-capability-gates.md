# ADR-045 — L9 hard capability gates (L9)

**Status:** ratified at L9. Implements Freeze Contract §13.8/§13.11 (capability-level
evaluation, release gates, no capability regression) and `LEVELS.md` L9
(Evaluation v1 = hard capability gates, isolation matrix, scale budgets).

## Context

The L0–L8 evaluation framework already provides golden cases per frozen
capability, per-level gates (l4/l5/l7/l8), an eval-runs history store, and a
deterministic capability-eval harness. What is missing is a **single L9 hard
capability gate** that evaluates the complete frozen capability set as a release
gate. L9 supplies that gate as an independent evaluation layer — it does not
create a second framework and does not re-gate or rewrite the existing L4–L8
gates.

## Decision

L9 hard capability gates:

- **`test_l9_eval_gate.py`** — an independent L9 evaluation gate that evaluates
  the **complete frozen capability set** (all 18 capabilities) using the existing
  capability-eval framework (`load_suite`, `validate_suite_coverage`,
  `load_golden_file`) and existing golden cases:
  - full-suite schema + coverage (every capability ≥5 phrasings, en + hi-en),
  - no capability regression against the frozen registry,
  - deterministic outcome checks for the deterministic operations (count,
    inventory, list, lookup, clarify/refuse) consistent with the L4/L5 gates.
- Reuses the existing golden cases, eval schema (`ALLOWED_GATE_LEVELS` already
  includes `l9`), and eval patterns. No new capability IDs, no re-gating of
  existing L4–L8 cases, no second evaluation framework.

## Rules

1. L9 evaluates the complete frozen capability set; it never adds a capability ID.
2. Existing golden cases (l4/l5/l7/l8) are reused unmodified; L9 adds only an
   independent gate over them.
3. Regression = capability regression, never phrase regression (Freeze §13.8.3).
4. No eval code influences production routing; the gate is a release gate.
5. No patch-farm code is introduced (Freeze §13.10).

## Consequences

Every release is gated on the full frozen capability set being green, consistent
with the anti-patch and capability-evaluation doctrine.
