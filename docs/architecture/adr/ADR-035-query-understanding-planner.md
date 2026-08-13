# ADR-035 — Model-driven query-understanding planner (L4)

**Status:** ratified at L4. Implements Freeze Contract §13.5.1 (query
understanding model-driven), §16 plan schema, ADR-020.

## Decision

A user question is turned into a **structured plan** by the L4 model-driven
planner via ``AiCore.gateway().structured_generate()``. The plan uses the
frozen schema: ``{operation, domains[], entities[], time_range, filters{},
output_kind, evidence_required, sub_plans[]}``.

- The planner NEVER executes model output directly.
- Every plan is validated by a deterministic ``PlanValidator`` (schema, types,
  bounded sizes, operation ∈ frozen capability registry) BEFORE any dispatch.
- Invalid/unsafe/unsupported plans are rejected and routed to clarify/refuse
  (ADR-020) — never executed, never substring-matched.
- The planner never queries data itself (§27); dispatch goes through the
  existing ACL-gated retrieval/grounded-QA path.

## Rules

1. Planner output is untrusted input.
2. Only validated plans are dispatched.
3. Planner failure → deterministic fast-path → clarify → refuse (ADR-020).
4. Hinglish/bilingual handling is model-driven (not regex); scope per Q9.
5. The planner uses the AI Core gateway (ADR-001), not a second LLM client.

## Consequences

A new phrasing of a question requires zero production routing code — it is
evaluation data (capability golden cases). The patch-farm regex/rules path is
removed from the active answering path.
