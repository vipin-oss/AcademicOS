"""Claim / fact representation (L1, ADR-002 + ADR-019).

A Claim is a single asserted-or-proposed fact: ``predicate_id`` (+ version,
from the registry-driven predicate catalogue) with a value that either
validates against the predicate's value schema or is kept as ``raw`` plus the
source text (never dropped).

Confidence is a SEPARATE concept from extraction confidence (ADR-004):

- ``extraction_confidence`` lives on spans / CDM / OCR text (the uncertainty of
  having read the source correctly).
- ``fact_confidence`` is on the Claim (the confidence that the extracted value
  IS the fact). For OCR/vision-derived claims it is capped at ``MEDIUM``.

The Claim lifecycle (ADR-006 / ADR-021):

- ``PROPOSED`` — candidate produced by an engine, not yet authoritative.
- ``CONFIRMED`` — human-approved (or ASSERTED); the only auto-usable truth.
- ``REJECTED`` — human-rejected; kept for audit, never auto-usable.
- ``SUPERSEDED`` — replaced by a newer version/fact (never deleted).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.domain.value_objects.enums import Provenance


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


#: OCR/vision-derived fact confidence is capped at medium (ADR-004).
MEDIUM_CONFIDENCE_CAP = 0.7


def confidence_tier(confidence: float) -> str:
    """Deterministic tier (ADR-004): high / medium / low."""
    if confidence >= 0.9:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    predicate_id: str
    predicate_version: int
    value_schema: str
    value: dict[str, Any]           # validated per predicate OR {"kind":"raw",...}
    source_document_id: str
    source_version: int
    status: ClaimStatus = ClaimStatus.PROPOSED
    provenance: Provenance = Provenance.INFERRED
    fact_confidence: float | None = None
    extraction_confidence: float | None = None
    acl_scope: str | None = None
    supersedes_claim_id: str | None = None
    spans: tuple[Any, ...] = ()    # Span objects (typing.Any to avoid cycle)

    def __post_init__(self) -> None:
        if self.fact_confidence is not None and not (
            0.0 <= self.fact_confidence <= 1.0
        ):
            raise ValueError("fact_confidence must be between 0.0 and 1.0")
        if self.extraction_confidence is not None and not (
            0.0 <= self.extraction_confidence <= 1.0
        ):
            raise ValueError("extraction_confidence must be between 0.0 and 1.0")

    @property
    def is_authoritative(self) -> bool:
        """Only CONFIRMED or ASSERTED claims are auto-usable by AI."""
        return self.status is ClaimStatus.CONFIRMED and (
            self.provenance is Provenance.ASSERTED
            or self.fact_confidence is None
            or self.fact_confidence >= 0.0
        )

    def superseded_by(self, new_claim_id: str) -> Claim:
        return Claim(
            claim_id=self.claim_id,
            predicate_id=self.predicate_id,
            predicate_version=self.predicate_version,
            value_schema=self.value_schema,
            value=self.value,
            source_document_id=self.source_document_id,
            source_version=self.source_version,
            status=ClaimStatus.SUPERSEDED,
            provenance=self.provenance,
            fact_confidence=self.fact_confidence,
            extraction_confidence=self.extraction_confidence,
            acl_scope=self.acl_scope,
            supersedes_claim_id=new_claim_id,
            spans=self.spans,
        )


__all__ = ["MEDIUM_CONFIDENCE_CAP", "Claim", "ClaimStatus", "confidence_tier"]
