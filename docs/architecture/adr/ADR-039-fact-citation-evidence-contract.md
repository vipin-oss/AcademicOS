# ADR-039 — Fact citation & confidence output contract (L6)

**Status:** ratified at L6. Implements Freeze Contract §13.6 (Evidence/Citation
Laws: citable set includes CONFIRMED/ASSERTED claims with source spans;
deterministic verification; bounded evidence; evidence traceability) and
ADR-025 (extraction vs fact confidence).

## Decision

L6 extends the existing object-citation model with **fact citations** and an
explicit **confidence output contract**, without a second evidence pipeline,
citation verifier, ACL system, or tool executor.

- **FactCitation**: a CONFIRMED/ASSERTED claim (per `Claim.is_authoritative`)
  made citable, carrying claim id, predicate, source document id + version, a
  polymorphic source span, the claim value, and a `ConfidenceView`.
- **ConfidenceView**: the backend confidence output contract preserving the
  repository's terminology (ADR-025): `fact_confidence` vs
  `extraction_confidence`, surfaced as deterministic tiers (high/medium/low)
  when the repository does not carry a numerical value.
- **EvidenceSet**: the bounded, deterministic set of evidence for an answer
  (object citations + fact citations), with deterministic ordering.

## Rules

1. Only CONFIRMED/ASSERTED claims are citable (ADR-006/ADR-019); superseded and
   rejected claims are never citable.
2. Claim citations are ACL-gated via the existing `PermissionEvaluator` +
   `object_acl_scope`; only claims/spans visible to the requesting principal are
   exposed (no citation leakage).
3. Citation numbering/order is deterministic; duplicates are removed
   deterministically.
4. Existing object/search-hit citations (`CitationBuilder`/`AnswerVerifier`)
   remain the verification authority and are unchanged.
5. `ClaimEvidenceService` reads the L1 `ClaimStore`; it does not create a second
   claim store, retrieval, ACL, or capability system.

## Consequences

Answers and APIs can expose citable facts with spans and confidence, while the
anti-hallucination and ACL guarantees of the existing citation pipeline are
preserved. L7 (memory) and L8 (cross-domain) consume the same evidence/citation
contract.
