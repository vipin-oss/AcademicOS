"""Document-type registry (ADR-053 — data, not code).

Wave 1 document types for the M6 deterministic classifier. Each type carries
the three deterministic rule families the classifier consults, in priority
order: filename patterns, heading keywords, issuer keywords. Adding a type
(or tuning its rules) is a data change — never a code change — so tenants can
extend the taxonomy without a deploy (the same ADR-019 additive-registry
doctrine, applied to document kinds).

``FAST_LOCAL`` tie-breaking is deliberately NOT here: the classifier is
deterministic-only and returns ``unknown`` on ambiguity (never a strong
model).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentTypeSpec:
    type_id: str
    name: str
    description: str
    filename_patterns: tuple[str, ...]
    heading_keywords: tuple[str, ...]
    issuer_keywords: tuple[str, ...]


#: Wave 1 document types (the two most common academic-administration
#: documents). Additive only.
DOCUMENT_TYPES: tuple[DocumentTypeSpec, ...] = (
    DocumentTypeSpec(
        type_id="grant_sanction_letter",
        name="Grant / Sanction Letter",
        description="A funding agency's letter sanctioning a research grant or project.",
        filename_patterns=("sanction", "grant", "award", "fund", "project"),
        heading_keywords=("sanction", "grant", "research grant", "sanction order", "award"),
        issuer_keywords=(
            "sanctioned amount", "principal investigator", "funding agency",
            "sanction order", "co-investigator", "research grant",
        ),
    ),
    DocumentTypeSpec(
        type_id="office_order",
        name="Office Order",
        description="An administrative office order, circular, or memorandum.",
        filename_patterns=("order", "circular", "memo", "notification"),
        heading_keywords=("office order", "circular", "memorandum", "notification", "memo"),
        issuer_keywords=(
            "office order", "issued", "competent authority", "registrar",
            "director", "in continuation", "circular",
        ),
    ),
)

_BY_ID: dict[str, DocumentTypeSpec] = {spec.type_id: spec for spec in DOCUMENT_TYPES}


def get_document_type(type_id: str) -> DocumentTypeSpec | None:
    return _BY_ID.get(type_id)


__all__ = ["DOCUMENT_TYPES", "DocumentTypeSpec", "get_document_type"]
