# ADR-034 — Extraction→claim bridge (L3)

**Status:** ratified at L3. Closes the L2 gap: L2 produced CDM blocks + content
projection but did not write document-derived claims. L3 adds a deterministic,
predicate-driven bridge.

## Decision

A **deterministic fact-extraction rule** maps specific NIR/CDM elements to
predicate-catalogue claims:

- It is keyed to the seed predicate catalogue (e.g. a table cell under an
  "Amount" header → `sanctioned_amount`; a "PI" field → `principal_investigator`;
  a date field → `issue_date`).
- It is **NOT** general NER/entity extraction (deferred).
- Unknown/unparseable values → `raw` + source text (ADR-019), never dropped.
- Each produced claim is `ClaimStatus.PROPOSED`, `Provenance.INFERRED`, with
  polymorphic `Span[]`, `fact_confidence` + `extraction_confidence`
  (OCR-derived capped at `MEDIUM_CONFIDENCE_CAP`), and `acl_scope`.

The bridge lives in `NirMapper.write_claims` and is invoked by the extraction
orchestrator (after CDM write), for both single documents and package members.

## Rules

1. The bridge is deterministic and idempotent (same input → same claims).
2. Claims generated from extraction remain `PROPOSED` — distinguishable from
   human-confirmed facts (L3 confirmation promotes them).
3. It writes via `ClaimService.propose` only; it never writes metadata.

## Consequences

L2-extracted content becomes confirmable facts in the L1 claim store, so the L3
confirmation/correction queue has real candidates to review.
