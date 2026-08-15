# ADR-030 — OCR policy (L2)

**Status:** ratified at L2. Implements OCR as a port-isolated, optional adapter.

## Decision

OCR is an **adapter/port**, not hardwired into application logic. It is
**feature-flagged OFF by default** (so CI/tests need no model download and
existing behavior is unchanged). When enabled:

- source image → OCR text + per-region/per-page **OCR confidence**
- OCR text is never silently merged with digital text
- OCR-derived **fact** confidence is capped at `MEDIUM_CONFIDENCE_CAP` (0.7,
  ADR-025) — OCR uncertainty is never confused with fact confidence
- `needs_ocr` remains the honest signal for scanned/zero-text sources

## Rules

1. OCR engine lives in `app.infrastructure.extraction.nir_ocr` behind
   `app.application.ports.ocr_engine.OcrEngine`.
2. OCR is optional; without it the source is reported honestly as needing OCR.
3. Low-confidence OCR is never auto-promoted to authoritative knowledge.
4. OCR confidence is stored separately from any fact confidence (ADR-025).

## Consequences

Scanned/image content becomes extractable without ever fabricating certainty.
A poor OCR run degrades honestly rather than inventing facts.
