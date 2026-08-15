"""Extraction templates (ADR-053 — data, not code).

An extraction template binds a document type to the set of predicates the
typed extractor is allowed to propose for it. It is the M6 "template" stage:
``classify -> template -> candidates``. Like the predicate catalogue and the
document-type registry, it is additive data — enabling or disabling a template
row is a config change, never a deploy (the blueprint's M6 rollback path).

Every predicate id referenced here must exist in the predicate catalogue
(enforced by the M6 guardrail).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionTemplateSpec:
    template_id: str
    document_type_id: str
    predicate_ids: tuple[str, ...]
    version: int = 1


#: Wave 1 templates (ADR-053). Additive only.
EXTRACTION_TEMPLATES: tuple[ExtractionTemplateSpec, ...] = (
    ExtractionTemplateSpec(
        template_id="grant_sanction_letter",
        document_type_id="grant_sanction_letter",
        predicate_ids=(
            "sanctioned_amount",
            "principal_investigator",
            "co_investigator",
            "project_title",
            "project_duration_months",
            "project_start_date",
            "project_end_date",
            "funding_agency",
            "scheme_name",
            "sanction_order_number",
            "file_number",
            "sanctioned_by",
            "overhead_amount",
            "first_year_amount",
            "recurring_amount",
            "grant_category",
            "issue_date",
            "department",
            "institution",
        ),
    ),
    ExtractionTemplateSpec(
        template_id="office_order",
        document_type_id="office_order",
        predicate_ids=(
            "order_number",
            "order_date",
            "subject",
            "issuing_authority",
            "addressee",
            "effective_date",
            "compliance_deadline",
            "purpose",
            "circular_number",
            "approval_reference",
            "file_number",
            "issue_date",
            "department",
            "sanctioned_by",
        ),
    ),
)

_BY_DOC_TYPE: dict[str, ExtractionTemplateSpec] = {
    spec.document_type_id: spec for spec in EXTRACTION_TEMPLATES
}


def get_template(document_type_id: str) -> ExtractionTemplateSpec | None:
    return _BY_DOC_TYPE.get(document_type_id)


def template_predicates(document_type_id: str) -> tuple[str, ...]:
    """The predicate ids a document type extracts, or () when unknown."""
    spec = _BY_DOC_TYPE.get(document_type_id)
    return spec.predicate_ids if spec is not None else ()


__all__ = [
    "EXTRACTION_TEMPLATES",
    "ExtractionTemplateSpec",
    "get_template",
    "template_predicates",
]
