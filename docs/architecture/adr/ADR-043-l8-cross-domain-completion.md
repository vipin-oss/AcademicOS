# ADR-043 — L8 Cross-Domain Completion (L8)

**Status:** ratified at L8. Implements Freeze Contract §13.9 (L8 = multi-hop,
absence, temporal, compare; prereq L4 + L5; consumed by L15) and the blueprint's
AI-reasoning architecture (§16/§17/§18/§19/§26).

## Context

The four L8 capabilities (`cross_domain`, `absence`, `temporal`, `compare`) are
already in the frozen capability registry and the L4 plan schema. The planner
emits `operation` + `sub_plans[]` for multi-step; the L5 `ToolExecutor` +
`InMemoryToolRegistry` provide the execution seam; `GraphRuntimeService` provides
ACL-filtered multi-hop traversal; the L6 evidence/citation pipeline and the L7
persistent memory (context-only) are available. What is missing is the
**execution** of these capabilities. L8 supplies that as additive execution
capabilities/tools — it does not build a new planner, retrieval, ACL, evidence,
or memory system.

## Decision

L8 is a **bounded multi-hop execution + cross-domain completion/synthesis layer**
that executes the four already-frozen capabilities through the existing L5 tool
execution seam:

- **cross_domain** — entity-anchored multi-hop: from a set of anchor entities,
  traverse typed relationships across object types (bounded depth ≤ 5, nodes ≤ 200,
  ACL-filtered at every hop via `PermissionEvaluator`/`object_acl_scope`), merging
  intermediate results into a structured, deterministically ordered cross-domain
  evidence set. Uses the L4 `sub_plans[]` structure when a plan decomposes into hops.
- **absence** — deterministic, ACL-aware negative/anti-join: "absent from the
  authorized/searchable scope" (never an absolute real-world claim). Distinguishes
  confirmed absence (within the queried authorized dataset) from insufficient
  evidence; never leaks unauthorized objects.
- **temporal** — deterministic, rules-based `time_range` resolution (this year,
  last year, after YYYY, as-of date, etc.), timezone-aware where the system provides
  a timezone, bounded and testable; no calendar data model, no temporal database.
- **compare** — deterministic contrast over authorized retrieved results, preserving
  source/evidence linkage, defining missing-value and ordering/tie behavior, never
  hallucinating values, producing structured comparison output for L6 citation assembly.

All tools are registered additively via the existing `build_tool_registry(...)`
hook and execute through the existing `ToolExecutor` (resolve → schema-validate →
ACL-gate → execute → normalize → audit). No new capability IDs are introduced; the
frozen 18-capability registry is unchanged.

## Multi-hop semantics (bounded)

- Depth bounded (≤ 5) and node count bounded (≤ 200), reusing
  `GraphRuntimeService` amplification guards.
- Deterministic traversal/order (BFS level-order, stable tie-breaks by object id).
- ACL filtering BEFORE exposing any intermediate result (pre-filter, never
  post-filter) — no hidden access through intermediate hops.
- No uncontrolled recursion, no arbitrary agent loop, no planner rewrite.
- Intermediate results stay structured (object id, type, title, relationship kind,
  path) so the final evidence/citation assembly can use them.

## Absence semantics

- Absence = within the ACL-visible/searchable set. A result is either
  `confirmed_absence` (the authorized scope was searched and the target is not
  present) or `insufficient_evidence` (scope ambiguous / could not be searched).
- Never an absolute claim about the real world.
- Never leaks objects the principal is not authorized to see.

## Temporal resolution semantics

- Deterministic rules over a `time_range` string; timezone-aware where the system
  provides one (else UTC).
- No new calendar/event persistence model. Bounded, testable, pure.

## Compare semantics

- Operates only on authorized results; preserves source/evidence linkage.
- Defines missing-value behavior and ordering/tie behavior.
- No hallucinated values; structured output consumable by L6 citations.

## Interaction with L4/L5/L6/L7

- **L4:** consumes validated plans (with `sub_plans`, `entities`, `time_range`).
  L4 planner/validator semantics are NOT modified.
- **L5:** registers additive tools through the existing registry/executor. L5
  executor/registry semantics are NOT modified.
- **L6:** cross-domain output feeds the existing evidence/citation assembly;
  only search-hit items + CONFIRMED/ASSERTED claims are citable. Graph-only
  neighbors are never citable (Freeze Contract §20/§21).
- **L7:** persistent memory is used only as context, never as evidence
  (ADR-015).

## ACL / determinism / error requirements

- Every tool is ACL-filtered through the existing L5 execution path; object-level
  ACL re-checked via `PermissionEvaluator`.
- Deterministic ordering everywhere; no randomness.
- Errors surface as deterministic `ToolResult(ok=False, error=…)` via
  `ToolExecutor`; no silent stall, no partial unverified answers leaked.

## Non-responsibilities

- NOT a second planner, retrieval system, ACL system, evidence/citation system,
  or memory system.
- NOT new capability IDs.
- NOT a new persistence layer (no migration unless the blueprint proves it
  necessary — none is required for L8).
- NOT the A8 agent runtime (Temporal/Kafka), external scholarly connectors,
  scheduled monitoring, or L9 evaluation / L15 agent surface.

## Consequences

The four L8 capabilities become executable through the existing pipeline with
full ACL, determinism, and evidence discipline, consumed by L15. The frozen
capability registry, L4 planner, L5 executor, L6 evidence, and L7 memory are
unchanged.
