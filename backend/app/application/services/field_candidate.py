"""Field candidate representation for reconciliation (Revision #5).

A common representation for both deterministic and AI-extracted fields,
enabling comparison, confidence scoring, and safe automation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FieldSource(str, Enum):
    """Where a field value came from."""
    LABEL = "label"          # Deterministic label extraction
    REGEX = "regex"          # Deterministic regex extraction
    PROSE = "prose"          # Deterministic prose pattern
    AI = "ai"                # AI extraction
    AGREEMENT = "agreement"  # Deterministic + AI agree
    USER = "user"            # User-provided


class FieldRisk(str, Enum):
    """Risk level for a field type."""
    LOW = "low"              # Safe to auto-apply (title, year, type)
    MEDIUM = "medium"        # Propose with confidence (authors, journal)
    HIGH = "high"            # Always review (DOI, financial amounts, identifiers)


class FieldStatus(str, Enum):
    """Status of a field candidate."""
    AUTO_APPLIED = "auto_applied"    # Safe + high confidence → auto-applied
    PROPOSED = "proposed"            # Medium confidence → user can accept
    REVIEW_REQUIRED = "review_required"  # Low confidence or conflict → needs review
    CONFLICT = "conflict"            # Deterministic != AI → needs review


@dataclass
class FieldCandidate:
    """One candidate value for a field, from any source."""
    predicate_id: str
    field_name: str
    value: str
    source: FieldSource
    confidence: float
    evidence: str = ""          # Original text span
    risk: FieldRisk = FieldRisk.MEDIUM
    status: FieldStatus = FieldStatus.PROPOSED


@dataclass
class ReconciledField:
    """A field after reconciliation between deterministic and AI extraction."""
    predicate_id: str
    field_name: str
    value: str
    confidence: float
    source: FieldSource
    status: FieldStatus
    risk: FieldRisk
    evidence: str = ""
    deterministic_value: str | None = None
    ai_value: str | None = None
    conflict: bool = False


# Risk classification for common fields
FIELD_RISK: dict[str, FieldRisk] = {
    # LOW risk - safe to auto-apply
    "publication_title": FieldRisk.LOW,
    "publication_year": FieldRisk.LOW,
    "conference_name": FieldRisk.LOW,
    "conference_acronym": FieldRisk.LOW,
    "event_title": FieldRisk.LOW,
    "issuing_authority": FieldRisk.LOW,
    "venue": FieldRisk.LOW,
    "city": FieldRisk.LOW,
    "country": FieldRisk.LOW,
    "recipient": FieldRisk.LOW,
    "editor_name": FieldRisk.LOW,

    # MEDIUM risk - propose with confidence
    "authors": FieldRisk.MEDIUM,
    "journal_name": FieldRisk.MEDIUM,
    "project_title": FieldRisk.MEDIUM,
    "funding_agency": FieldRisk.MEDIUM,
    "principal_investigator": FieldRisk.MEDIUM,
    "co_investigator": FieldRisk.MEDIUM,
    "awarding_body": FieldRisk.MEDIUM,
    "conference_organizer": FieldRisk.MEDIUM,
    "participation_type": FieldRisk.MEDIUM,
    "presentation_title": FieldRisk.MEDIUM,
    "presentation_type": FieldRisk.MEDIUM,

    # HIGH risk - always review
    "doi": FieldRisk.HIGH,
    "issn": FieldRisk.HIGH,
    "isbn": FieldRisk.HIGH,
    "sanctioned_amount": FieldRisk.HIGH,
    "invoice_amount": FieldRisk.HIGH,
    "sanction_order_number": FieldRisk.HIGH,
    "invoice_number": FieldRisk.HIGH,
    "certificate_number": FieldRisk.HIGH,
    "manuscript_id": FieldRisk.HIGH,
    "reference_number": FieldRisk.HIGH,
    "project_duration_months": FieldRisk.HIGH,
}


def get_field_risk(predicate_id: str) -> FieldRisk:
    """Get the risk level for a field type."""
    return FIELD_RISK.get(predicate_id, FieldRisk.MEDIUM)


__all__ = [
    "FieldCandidate",
    "FieldRisk",
    "FieldSource",
    "FieldStatus",
    "FIELD_RISK",
    "ReconciledField",
    "get_field_risk",
]
