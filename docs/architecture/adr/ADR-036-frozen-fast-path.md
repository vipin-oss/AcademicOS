# ADR-036 — Frozen deterministic fast-path (L4)

**Status:** ratified at L4. Implements Freeze Contract §13.5.2 (deterministic
fast-path ≤15 frozen commands; the list cannot grow), ADR-020.

## Decision

A bounded, explicit, deterministic fast-path of **≤15 commands** executes
OFFLINE (no LLM) for the most common operations: `inventory, lookup, list,
search, count, filter, timeline, navigate, aggregate, summarize, document_qa,
relationship, absence, clarify, refuse`.

- `FAST_PATH_COMMANDS` is the frozen contract. It MUST NOT silently grow.
- A guardrail pins its length to ≤15 and its exact membership.
- Every generated plan is validated against the frozen plan schema and the
  fast-path command set before dispatch.
- When the planner is unavailable, a small deterministic keyword router maps a
  question to a fast-path command; otherwise clarify/refuse (ADR-020).
- New commands go through the planner / capability registry, never the
  fast-path.

## Rules

1. The fast-path list is frozen and cannot grow (guardrail-enforced).
2. Fast-path commands execute deterministically and offline.
3. The fast-path is NOT a phrase→intent patch farm — it is bounded, explicit,
   and tied to the frozen capability registry.

## Consequences

Common questions are answered cheaply and deterministically without an LLM,
while the anti-patch guarantee holds: the fast-path cannot grow and never
becomes a hidden regex intent table.
