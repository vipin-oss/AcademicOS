# ADR-038 — Tool evaluation gate (L5)

**Status:** ratified at L5. Activates the existing `gate_level="l5"` golden
cases against real tool behavior.

## Decision

L5 evaluation verifies actual tool-layer behavior (not merely that classes
exist) using the frozen L0 capability-evaluation framework.

- The repository already contains `gate_level="l5"` golden cases across 16
  capability files (inventory, count, list, lookup, filter, aggregate, search,
  timeline, document_qa, relationship, summarize, compare, absence, temporal,
  navigate, cross_domain).
- The L5 gate runs these cases against the real tool executor and asserts
  deterministic outcomes (retrieval includes required types, counts correct,
  ACL isolation, no named-document leak).
- The frozen L0 evaluation framework is NOT modified; L5 adds cases/tests on
  top.

## Rules

1. Do not weaken or delete existing golden cases.
2. The gate verifies real tool behavior, not class presence.
3. Deterministic outcomes only.

## Consequences

L5 tools are verified at the capability level, consistent with the anti-patch
and capability-evaluation doctrine.
