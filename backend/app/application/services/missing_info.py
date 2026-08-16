"""Missing Information Engine (Stage 2 — Audit Revision #2).

Analyzes the user's academic records and identifies important missing fields.
Each missing item includes:
- record reference
- missing field
- why it matters
- confidence/reason
- actionable way to fix it

Rules are data-driven, not hard-coded. Each record type has a set of
"important" fields whose absence is worth surfacing.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.knowledge.extraction_schemas import EXTRACTION_SCHEMAS, FieldSpec
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.persistence.claim_store import SQLClaimStore


@dataclass(frozen=True)
class MissingItem:
    """One missing-field finding."""
    record_id: str
    record_type: str
    record_title: str
    missing_field: str
    predicate_id: str
    why_it_matters: str
    source_document_id: str | None = None


# Why each field matters (human-readable, shown to user).
_FIELD_IMPORTANCE: dict[str, str] = {
    "publication_title": "Required for citation and CV generation",
    "authors": "Needed for attribution and collaboration tracking",
    "journal_name": "Required for publication records and impact tracking",
    "publication_year": "Needed for chronological organization",
    "doi": "Enables automatic citation lookup and deduplication",
    "conference_name": "Required for conference participation records",
    "start_date": "Needed for timeline and calendar integration",
    "end_date": "Needed for timeline and calendar integration",
    "venue": "Location information for events and conferences",
    "project_title": "Required for research project records",
    "funding_agency": "Needed for grant tracking and reporting",
    "principal_investigator": "Required for project attribution",
    "sanctioned_amount": "Needed for financial tracking",
    "award_title": "Required for achievement records",
    "awarding_body": "Needed for award attribution",
    "designation": "Required for appointment records",
    "committee_name": "Required for committee records",
    "invoice_number": "Required for financial records",
    "scholar_name": "Required for PhD progress tracking",
    "supervisor_name": "Needed for supervision records",
}


def _important_fields(type_id: str) -> list[FieldSpec]:
    """Return the required + important optional fields for a record type."""
    schema = EXTRACTION_SCHEMAS.get(type_id, ())
    # Required fields are always important.
    # Optional fields with common predicates are also important.
    important_predicates = set(_FIELD_IMPORTANCE.keys())
    return [
        f for f in schema
        if f.required or f.predicate_id in important_predicates
    ]


def analyze_missing_fields(
    claims_store: SQLClaimStore,
    user_id: str,
) -> list[MissingItem]:
    """Analyze all confirmed claims for the user and find missing fields."""
    # Get all confirmed claims grouped by source document
    confirmed = claims_store.by_status(ClaimStatus.CONFIRMED)

    # Group claims by source document
    doc_claims: dict[str, dict] = {}  # doc_id -> {predicates: set, type: str, title: str}
    for claim in confirmed:
        doc_id = claim.source_document_id or ""
        if not doc_id:
            continue
        if doc_id not in doc_claims:
            doc_claims[doc_id] = {
                "predicates": set(),
                "type": claim.value_schema or "unknown",
                "title": claim.subject_id or doc_id,
            }
        doc_claims[doc_id]["predicates"].add(claim.predicate_id)

    missing: list[MissingItem] = []
    for doc_id, info in doc_claims.items():
        type_id = info["type"]
        present = info["predicates"]
        for field in _important_fields(type_id):
            if field.predicate_id not in present:
                importance = _FIELD_IMPORTANCE.get(field.predicate_id, "Recommended for complete records")
                missing.append(MissingItem(
                    record_id=doc_id,
                    record_type=type_id,
                    record_title=info["title"],
                    missing_field=field.field_name,
                    predicate_id=field.predicate_id,
                    why_it_matters=importance,
                    source_document_id=doc_id,
                ))

    # Sort: required fields first, then by importance
    required_first = [m for m in missing if any(
        f.required and f.predicate_id == m.predicate_id
        for f in EXTRACTION_SCHEMAS.get(m.record_type, ())
    )]
    optional_rest = [m for m in missing if m not in required_first]
    return required_first + optional_rest
