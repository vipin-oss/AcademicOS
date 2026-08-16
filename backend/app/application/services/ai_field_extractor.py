"""AI field extraction adapter (Revision #5).

Converts AI enrichment results (title, summary, tags, categories, keywords)
into field candidates compatible with the reconciliation engine.

This adapter bridges the existing EnrichmentResult with the new field
candidate representation, enabling comparison with deterministic extraction.
"""

from __future__ import annotations

from app.application.dtos.ai import EnrichmentResult
from app.application.services.field_candidate import (
    FieldCandidate,
    FieldSource,
    get_field_risk,
)


def enrichment_to_candidates(
    enrichment: EnrichmentResult,
    document_type_id: str | None,
) -> list[FieldCandidate]:
    """Convert an EnrichmentResult into field candidates for reconciliation.

    Maps enrichment fields to extraction schema predicates where possible.
    """
    candidates: list[FieldCandidate] = []

    if not enrichment.available:
        return candidates

    # Map enrichment title to publication_title (most common case)
    if enrichment.title:
        candidates.append(FieldCandidate(
            predicate_id="publication_title",
            field_name="title",
            value=enrichment.title,
            source=FieldSource.AI,
            confidence=0.80,  # AI extraction base confidence
            evidence=f"AI enrichment: {enrichment.title[:100]}",
            risk=get_field_risk("publication_title"),
        ))

    # Map enrichment tags to keywords
    for tag in enrichment.tags[:5]:  # Limit to top 5
        candidates.append(FieldCandidate(
            predicate_id="keywords",
            field_name="keywords",
            value=tag,
            source=FieldSource.AI,
            confidence=0.75,
            evidence=f"AI tag: {tag}",
            risk=get_field_risk("keywords"),
        ))

    return candidates


def extraction_result_to_candidates(
    fields: list[dict],
) -> list[FieldCandidate]:
    """Convert AI extraction fields (from DocumentIntakeService.ai_extractor)
    into field candidates for reconciliation.

    Each field dict should have: predicate_id, field_name, value, confidence, evidence
    """
    candidates: list[FieldCandidate] = []

    for f in fields:
        if not f.get("value"):
            continue
        candidates.append(FieldCandidate(
            predicate_id=f.get("predicate_id", ""),
            field_name=f.get("field_name", ""),
            value=str(f["value"]),
            source=FieldSource.AI,
            confidence=float(f.get("confidence", 0.75)),
            evidence=f.get("evidence", ""),
            risk=get_field_risk(f.get("predicate_id", "")),
        ))

    return candidates


__all__ = [
    "enrichment_to_candidates",
    "extraction_result_to_candidates",
]
