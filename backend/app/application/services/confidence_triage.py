"""Confidence triage for the confirmation queue (L3, ADR-033).

Deterministic ordering of PROPOSED candidates by human-review priority:
low/OCR-uncertain first, then medium, then high; stable tie-break by id.
Extraction confidence and fact confidence are kept separate (ADR-025).
"""

from __future__ import annotations

from app.domain.value_objects.claim import confidence_tier

#: Order: lower tier index = higher review priority.
_TIER_ORDER = {"low": 0, "medium": 1, "high": 2}


def triage_key(
    *,
    fact_confidence: float | None,
    needs_ocr: bool,
    subject_id: str,
) -> tuple[int, int, str]:
    """A sort key ordering candidates by review priority.

    Low-confidence and OCR-uncertain candidates sort first. ``subject_id`` is a
    deterministic tie-break.
    """
    tier = confidence_tier(fact_confidence) if fact_confidence is not None else "low"
    ocr_rank = 0 if needs_ocr else 1
    return (_TIER_ORDER.get(tier, 0), ocr_rank, subject_id)
