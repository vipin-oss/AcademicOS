"""L6 evidence & citation extension contracts (Freeze Contract §13.6).

Additive to the existing object-citation model:

- ``FactCitation`` — a CONFIRMED/ASSERTED claim made citable, with its source
  span and authoritative status. Distinct from the existing object/search-hit
  citation (``AssistantCitation``).
- ``ConfidenceView`` — the backend confidence output contract. It preserves the
  repository's terminology (ADR-025): extraction confidence vs fact/claim
  confidence, surfaced as deterministic tiers (high/medium/low) when no
  numerical confidence is defined.
- ``EvidenceSet`` — the bounded, deterministic set of evidence actually used
  for an answer (object citations + fact citations), with deterministic
  ordering.

These are output-contract DTOs only (stdlib). They do NOT create a second
evidence pipeline, citation verifier, ACL system, or tool executor — they
reuse the existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfidenceView:
    """Backend confidence output contract (ADR-025).

    Preserves extraction vs fact confidence as the repository defines them.
    Tiers (high/medium/low) are used when the repository does not carry a
    numerical confidence.
    """

    fact_confidence: float | None = None
    extraction_confidence: float | None = None
    fact_tier: str | None = None
    extraction_tier: str | None = None


@dataclass(frozen=True)
class FactCitation:
    """A citable CONFIRMED/ASSERTED claim with its source span.

    ``number`` is the deterministic per-answer citation index; ``claim_id`` is
    the stable identity. Only claims visible to the requesting principal and in
    an authoritative status (``Claim.is_authoritative``) are exposed.
    """

    number: int
    claim_id: str
    predicate_id: str
    source_document_id: str
    source_version: int
    span: dict | None = None        # polymorphic Span region dict (or None)
    value: object | None = None     # the claim's normalized/raw value
    confidence: ConfidenceView = field(default_factory=ConfidenceView)
    authoritative: bool = True


@dataclass(frozen=True)
class EvidenceSet:
    """Deterministic, bounded evidence used for one answer.

    ``object_citations`` are the existing search-hit citations (unchanged);
    ``fact_citations`` are the L6 claim citations. Ordering is deterministic.
    """

    object_citations: tuple = ()
    fact_citations: tuple[FactCitation, ...] = ()

    def __len__(self) -> int:
        return len(self.object_citations) + len(self.fact_citations)


__all__ = [
    "ConfidenceView",
    "EvidenceSet",
    "FactCitation",
]
