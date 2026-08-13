# ADR-025 — Extraction confidence vs fact confidence (L1)

**Status:** ratified at L1. Implements Freeze-Contract ADR-004 (confidence
composition rule: engine × OCR × corroboration × gazetteer; OCR-derived values
capped at medium; tiers high/medium/low).

## Decision

Confidence is kept as **two distinct concepts**, never collapsed:

- **extraction confidence** — on the span / CDM block / OCR text: the
  uncertainty of having *read the source* correctly.
- **fact confidence** — on the Claim: the confidence that the extracted value
  *is the fact*.

OCR/vision-derived **fact** confidence is capped at **medium** (`0.7`).
`confidence_tier()` maps a confidence to high/medium/low deterministically.

## Rules

1. Claims carry both `fact_confidence` and `extraction_confidence`.
2. CDM blocks carry `extraction_confidence` (they are extracted structure, not
   facts).
3. The ADR-004 composition rule is applied when a claim is derived from an
   extracted value; OCR-derived facts never exceed the medium cap.
4. Low-confidence extraction must never be silently promoted to authoritative
   knowledge; the confirmation inbox distinguishes candidates from canonical.

## Consequences

A blurry scan can carry low extraction confidence even when a human confirms
the resulting fact — the two uncertainties remain separable for evidence and
audit.
