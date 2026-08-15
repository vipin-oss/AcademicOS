# ADR-033 — Confidence triage for the confirmation queue (L3)

**Status:** ratified at L3. Implements Freeze-Contract ADR-004.

## Decision

The confirmation queue orders PROPOSED candidates deterministically by human-
review priority:

1. **confidence tier** (`claim.confidence_tier`: low/medium/high) — low-confidence
   and OCR-uncertain items surface first (they need human eyes);
2. **`needs_ocr` / OCR-uncertainty** flag — OCR-derived candidates ranked up;
3. **`created_at` / id** — stable deterministic tie-break.

Extraction confidence and fact confidence are kept separate (ADR-025) and both
surfaced; OCR-derived fact confidence is capped at `MEDIUM_CONFIDENCE_CAP`
(0.7).

## Rules

1. Low/OCR-uncertain facts are **never auto-promoted** — only a human
   CONFIRMED/ASSERTED action promotes.
2. Triage is deterministic and paginated (batch operations, bounded memory).
3. The queue enforces ACL before returning candidates (no cross-scope leakage).

## Consequences

Reviewers focus on uncertain candidates first, while confident candidates can
be batch-approved without risking silent promotion of unreliable extractions.
