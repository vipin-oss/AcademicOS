# ADR-037 — Tool registry & execution (L5)

**Status:** ratified at L5. Implements Freeze Contract §18 (tool registry shape)
and §13.5.6 (tools carry the principal; planner never queries data; every tool
call logged for audit).

## Decision

L5 is the **Tool Layer**: a frozen, explicit tool registry and a single
execution seam.

- Each tool has the frozen registry contract `{name, input_schema,
  output_schema, acl_scope, deterministic, cost_class}`.
- The registry is explicit (no hidden dynamic discovery), duplicate-name
  protected, and deterministic in lookup.
- The **tool executor** is the only path every tool call goes through. It:
  1. resolves the tool,
  2. validates input against the input_schema,
  3. enforces ACL on the tool's `acl_scope` for the principal,
  4. executes the tool,
  5. normalizes/validates output,
  6. records an audit row (idempotent by `call_id`),
  7. returns a deterministic structured result/error.
- Tools carry the user's principal; the executor passes it through and ACL-gates
  before dispatch. Callers cannot bypass the executor.
- Tool execution reuses existing services (ObjectRepository, retrieval, graph,
  grounded-QA); it does NOT create a second retrieval or ACL system.
- The L4 planner never queries data directly — it dispatches tool operations
  through the executor.

## Rules

1. The registry is additive-only; tools are registered explicitly at composition.
2. The executor is the sole execution path (no bypass).
3. ACL is enforced at the tool boundary using the existing `PermissionEvaluator`.
4. Tool calls are audited (idempotent by `call_id`); sensitive payloads are not
   stored.

## Consequences

L6 (evidence/citations) and L7 (memory) consume L5 tools as the execution layer;
L8 (cross-domain) chains tools. Tooling stays frozen/additive and ACL-gated.
