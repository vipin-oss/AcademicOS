# ADR-041 — L7 Memory v2 persistent layer (L7)

**Status:** ratified at L7. Implements Freeze Contract §13.7 (L7 = persistent
memory, prereq L1 + L5, consumed by L8) and the ratified L7 Decision Memo.

## Context

The current assistant "memory" (Sprint-8) is **conversation recall**: hybrid
search scoped to `ai_conversation` + graph, review-ranked, consolidation
(Jaccard ≥ 0.7 supersede-not-delete) — with **no persistent knowledge layer**
(Freeze Contract audit line 39). The `MEMORY_ARTIFACT`/`PROACTIVE_INSIGHT`
enum members had **no data model**. L7 fills that gap with a durable,
principal-scoped, provenance-carrying memory layer that is **context, never
evidence** (ADR-015).

## Decision

L7 delivers **persistent memory** as durable `UniversalObject` records
(`object_type = memory_artifact`) stored as **metadata on the existing
`objects` table**. **No new table, no migration.**

- **Content model** — a memory artifact carries `question`, `answer`,
  `content_hash`, `source_ids`, `review_status`, `provenance`, `acl_scope`,
  `version`, `created_at`, and a title.
- **Lifecycle** — `ACTIVE` (recallable, review-gated) ↔ `SUPERSEDED`
  (forgotten, hidden from recall, never deleted). Reuses `ObjectStatus` and
  `UniversalObject.supersede`.
- **Provenance** — `ASSERTED` (user-authored, immutable to AI per FR-MET-009),
  `INFERRED`/`SYSTEM` (AI/platform-derived). User-authored artifacts default to
  `approved`; system/AI-derived default to `pending` (review gate).
- **Review gate** — pending/rejected artifacts recall with **empty content**.
  Reuses the assistant review vocabulary.
- **ACL** — each artifact carries object ACL metadata; reads are pre-filtered
  through the existing `PermissionEvaluator` (`object_acl_scope`). No leakage.
- **Reuse** — `ObjectRepository`, `UniversalObject`, `PermissionEvaluator`,
  `object_acl_scope`, `MetadataEntry`/`MetadataLayer`/`Provenance`,
  `MemoryConsolidationService` (for conversation consolidation), the L5
  `ToolExecutor`/registry, and the `AssistantMemoryRetriever` port.
- **No second system** — L7 does not create a second memory store, retrieval
  system, ACL system, planner, tool registry, or evidence system.

## Rules

1. Memory is **context, never evidence** (ADR-015); it never feeds the L6
   citation/evidence contract.
2. Only CONFIRMED/APPROVED or empty-review content is recalled with content;
   pending/rejected content is never leaked.
3. Only ACL-visible artifacts are recalled (pre-filter, never post-filter).
4. User-authored (`ASSERTED`) memory is immutable to machine writes
   (FR-MET-009).
5. `forget` marks SUPERSEDED (no delete); SUPERSEDED artifacts are hidden from
   recall.
6. Deterministic ordering (relevance desc, then artifact id asc); bounded
   recall.

## Storage decision

Stored as `UniversalObject` metadata on the existing `objects` table (no new
table, no Alembic migration). Rationale: smallest correct solution, no
duplicate persistence abstraction, reuses ACL/provenance/versioning/supersede/
review, future-L8 compatible, deterministic. A dedicated `0015` table was
explicitly rejected under the "no migration unless genuinely required" rule.

## Consequences

The assistant gains a durable, recallable, principal-isolated memory layer that
L8 cross-domain can consume, without altering the L1 claim/span schema, the L4
planner, the L5 tool executor/registry, or the L6 evidence/citation contract.
