"""Input validation for the Faculty Management use cases.

Mirrors ``validators/research.py``: boundary validation before the domain is
touched; raises the application-layer ``ValidationError``.
"""
from __future__ import annotations

import re

from app.application.dtos.faculty import (
    EMPLOYMENT_TYPES,
    PROFILE_SECTION_KEYS,
    CreateFacultyInput,
    UpdateFacultyInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_faculty import ListFacultyQuery
from app.domain.value_objects.enums import ObjectStatus

_DATE_RE = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")
_URL_RE = re.compile(r"^https?://\S+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_YEAR_RE = re.compile(r"^\d{4}$")

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


def _check_status(errors: list[str], status: ObjectStatus | None) -> None:
    if status is not None and status not in _CREATABLE_STATUSES:
        errors.append(f"status must be one of: {', '.join(s.value for s in _CREATABLE_STATUSES)}.")


def _check_sections(errors: list[str], sections: dict[str, list[dict] | None]) -> None:
    """Every profile section entry must be a dict carrying its declared fields."""
    for key, items in sections.items():
        if items is None:
            continue
        declared = PROFILE_SECTION_KEYS[key]
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{key}[{index}] must be an object.")
                continue
            populated = [field for field, value in item.items() if str(value or "").strip()]
            if not populated:
                errors.append(f"{key}[{index}] is empty.")
            unknown = [field for field in item if field not in declared]
            if unknown:
                errors.append(
                    f"{key}[{index}] has unknown fields: {', '.join(sorted(unknown))}."
                )
            year = item.get("year")
            if year is not None and str(year).strip() and not _YEAR_RE.match(str(year).strip()):
                errors.append(f"{key}[{index}].year must be a 4-digit year.")


class _Checks:
    """Shared scalar checks for create/update (update passes only present fields)."""

    @staticmethod
    def common(
        errors: list[str],
        *,
        joining_date: str | None,
        employment_type: str | None,
        email: str | None,
        orcid: str | None,
        website: str | None,
        sections: dict[str, list[dict] | None],
        committees: list[str] | None,
    ) -> None:
        if joining_date not in (None, "") and not _DATE_RE.match(str(joining_date)):
            errors.append("joining_date must be YYYY, YYYY-MM, or YYYY-MM-DD.")
        if employment_type not in (None, "") and employment_type not in EMPLOYMENT_TYPES:
            errors.append(
                f"employment_type must be one of: {', '.join(EMPLOYMENT_TYPES)} "
                f"(free-text designations are allowed, the employment type is not)."
            )
        if email not in (None, "") and not _EMAIL_RE.match(str(email)):
            errors.append("email is not a valid email address.")
        if orcid not in (None, "") and not _ORCID_RE.match(str(orcid)):
            errors.append("orcid must look like 0000-0002-1825-0097.")
        if website not in (None, "") and not _URL_RE.match(str(website)):
            errors.append("website must start with http:// or https://.")
        _check_sections(errors, sections)
        if committees is not None:
            for index, target in enumerate(committees):
                if not str(target).strip():
                    errors.append(f"committees[{index}] must not be empty.")


def assert_valid_create_faculty_input(data: CreateFacultyInput) -> None:
    errors: list[str] = []
    if not data.name or not data.name.strip():
        errors.append("name must not be empty.")
    if not data.employee_id or not data.employee_id.strip():
        errors.append("employee_id must not be empty.")
    if not data.created_by or not data.created_by.strip():
        errors.append("created_by must not be empty.")
    _check_status(errors, data.status)
    _Checks.common(
        errors,
        joining_date=data.joining_date,
        employment_type=data.employment_type,
        email=data.email,
        orcid=data.orcid,
        website=data.website,
        sections={
            "degrees": data.degrees,
            "experience": data.experience,
            "awards": data.awards,
            "memberships": data.memberships,
            "certifications": data.certifications,
            "admin_positions": data.admin_positions,
        },
        committees=data.committees,
    )
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_faculty_input(data: UpdateFacultyInput) -> None:
    errors: list[str] = []
    if data.name is not None and not data.name.strip():
        errors.append("name must not be empty.")
    if data.employee_id is not None and not data.employee_id.strip():
        errors.append("employee_id must not be empty.")
    if not data.actor or not data.actor.strip():
        errors.append("actor must not be empty.")
    _check_status(errors, data.status)
    _Checks.common(
        errors,
        joining_date=data.joining_date,
        employment_type=data.employment_type,
        email=data.email,
        orcid=data.orcid,
        website=data.website,
        sections={
            "degrees": data.degrees,
            "experience": data.experience,
            "awards": data.awards,
            "memberships": data.memberships,
            "certifications": data.certifications,
            "admin_positions": data.admin_positions,
        },
        committees=data.committees,
    )
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_faculty_query(query: ListFacultyQuery) -> None:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if not 1 <= query.page_size <= 100:
        errors.append("page_size must be between 1 and 100.")
    if errors:
        raise ValidationError("; ".join(errors))
