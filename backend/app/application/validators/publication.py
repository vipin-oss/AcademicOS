"""Input validation for publication use cases.

Mirrors ``validators/object.py`` / ``validators/document.py``: boundary
validation before the domain is touched; raises the application-layer
``ValidationError``. Pure and framework-free.
"""
from __future__ import annotations

import re

from app.application.dtos.publication import (
    LINK_GROUPS,
    CreatePublicationInput,
    UpdatePublicationInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_publications import ListPublicationsQuery
from app.application.services.bibliography import PUBLICATION_TYPES
from app.domain.value_objects.enums import ObjectStatus

# FR-PUB-001 lifecycle expressed as metadata (Blueprint §1.4 type extension).
PIPELINE_STAGES = (
    "idea",
    "draft",
    "internal_review",
    "submitted",
    "under_review",
    "revision",
    "accepted",
    "published",
    "post_publication",
)

QUARTILES = ("Q1", "Q2", "Q3", "Q4")

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_DATE_RE = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")
_URL_RE = re.compile(r"^https?://\S+$")


def _validate_common_fields(errors: list[str], **fields) -> None:
    if fields.get("publication_type") is not None and fields["publication_type"] not in (
        PUBLICATION_TYPES
    ):
        errors.append(f"publication_type must be one of: {', '.join(PUBLICATION_TYPES)}.")
    if fields.get("pipeline_stage") is not None and fields["pipeline_stage"] not in PIPELINE_STAGES:
        errors.append(f"pipeline_stage must be one of: {', '.join(PIPELINE_STAGES)}.")
    if fields.get("quartile") is not None and fields["quartile"] not in QUARTILES:
        errors.append("quartile must be one of: Q1, Q2, Q3, Q4.")
    doi = fields.get("doi")
    if doi and not _DOI_RE.match(doi):
        errors.append("doi must look like '10.xxxx/…'.")
    year = fields.get("year")
    if year is not None and not (1000 <= int(year) <= 2100):
        errors.append("year must be between 1000 and 2100.")
    date = fields.get("date")
    if date and not _DATE_RE.match(date):
        errors.append("date must be YYYY, YYYY-MM, or YYYY-MM-DD.")
    citation_count = fields.get("citation_count")
    if citation_count is not None and int(citation_count) < 0:
        errors.append("citation_count must not be negative.")
    impact_factor = fields.get("impact_factor")
    if impact_factor is not None and float(impact_factor) < 0:
        errors.append("impact_factor must not be negative.")
    url = fields.get("publisher_url")
    if url and not _URL_RE.match(url):
        errors.append("publisher_url must be an http(s) URL.")
    for author in fields.get("authors") or ():
        if not str(author.get("name", "")).strip():
            errors.append("Every author needs a non-empty name.")
            break
        orcid = author.get("orcid")
        if orcid and not _ORCID_RE.match(orcid):
            errors.append(f"Invalid ORCID for author {author['name']!r} (0000-0002-1825-0097 form).")
            break
    links = fields.get("links")
    if links:
        for group in links:
            if group not in LINK_GROUPS:
                errors.append(f"Unknown link group: {group!r} (expected one of {', '.join(LINK_GROUPS)}).")


def validate_create_publication_input(dto: CreatePublicationInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Title must not be empty.")
    if not dto.uploaded_by or not dto.uploaded_by.strip():
        errors.append("uploaded_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_common_fields(
        errors,
        publication_type=dto.publication_type,
        pipeline_stage=dto.pipeline_stage,
        quartile=dto.quartile,
        doi=dto.doi,
        year=dto.year,
        date=dto.date,
        citation_count=dto.citation_count,
        impact_factor=dto.impact_factor,
        publisher_url=dto.publisher_url,
        authors=dto.authors,
        links=dto.links,
    )
    return errors


def validate_update_publication_input(dto: UpdatePublicationInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Title must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_common_fields(
        errors,
        publication_type=dto.publication_type,
        pipeline_stage=dto.pipeline_stage,
        quartile=dto.quartile,
        doi=dto.doi,
        year=dto.year,
        date=dto.date,
        citation_count=dto.citation_count,
        impact_factor=dto.impact_factor,
        publisher_url=dto.publisher_url,
        authors=dto.authors,
        links=dto.links,
    )
    return errors


def validate_list_publications_query(query: ListPublicationsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1:
        errors.append("page_size must be >= 1.")
    if query.page_size > 100:
        errors.append("page_size must be <= 100.")
    if query.publication_type is not None and query.publication_type not in PUBLICATION_TYPES:
        errors.append(f"publication_type must be one of: {', '.join(PUBLICATION_TYPES)}.")
    if query.quartile is not None and query.quartile not in QUARTILES:
        errors.append("quartile must be one of: Q1, Q2, Q3, Q4.")
    if query.pipeline_stage is not None and query.pipeline_stage not in PIPELINE_STAGES:
        errors.append(f"pipeline_stage must be one of: {', '.join(PIPELINE_STAGES)}.")
    if query.year is not None and not (1000 <= int(query.year) <= 2100):
        errors.append("year must be between 1000 and 2100.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    return errors


def assert_valid_create_publication_input(dto: CreatePublicationInput) -> None:
    errors = validate_create_publication_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_publication_input(dto: UpdatePublicationInput) -> None:
    errors = validate_update_publication_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_publications_query(query: ListPublicationsQuery) -> None:
    errors = validate_list_publications_query(query)
    if errors:
        raise ValidationError("; ".join(errors))
