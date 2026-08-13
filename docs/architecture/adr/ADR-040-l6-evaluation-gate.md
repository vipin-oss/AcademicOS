# ADR-040 — L6 evaluation gate (L6)

**Status:** ratified at L6. Activates an L6 evaluation gate using the existing
L0 capability-evaluation framework.

## Decision

L6 adds a focused evaluation gate (mirroring the L5 gate in ADR-038) that
verifies actual L6 behavior against the frozen evidence/citation laws:

- CONFIRMED/ASSERTED claims produce citable fact citations with source spans.
- Source-span preservation and deterministic citation numbering/dedup.
- ACL filtering: claims/spans not visible to the principal are excluded; no
  citation leakage across principals.
- Confidence contract (extraction vs fact tiers).
- Existing object/search-hit citations remain functional.
- Empty/no-evidence behavior is deterministic.

## Rules

1. The frozen L0 evaluation framework is NOT modified; L6 adds cases/tests on
   top.
2. Existing golden cases (l4/l5/l9) are not weakened, skipped, or rewritten.
3. The gate tests real behavior, not class presence.

## Consequences

L6 fact-citation and confidence behavior is verified at the capability level,
consistent with the anti-patch and capability-evaluation doctrine.
