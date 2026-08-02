"""Input validation for student use cases.

Mirrors ``validators/publication.py``: boundary validation before the domain
is touched; raises the application-layer ``ValidationError``.
"""
from __future__ import annotations

import re

from app.application.dtos.student import (
    LINK_GROUPS,
    STUDENT_TYPES,
    CreateStudentInput,
    UpdateStudentInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_students import ListStudentsQuery
from app.domain.value_objects.enums import ObjectStatus

_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")
_URL_RE = re.compile(r"^https?://\S+$")

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


def _validate_common(errors: list[str], **fields) -> None:
    student_type = fields.get("student_type")
    if student_type is not None and student_type not in STUDENT_TYPES:
        errors.append(f"student_type must be one of: {', '.join(STUDENT_TYPES)}.")
    semester = fields.get("semester")
    if semester is not None:
        try:
            if not 1 <= int(semester) <= 12:
                errors.append("semester must be between 1 and 12.")
        except (TypeError, ValueError):
            errors.append("semester must be a number between 1 and 12.")
    email = fields.get("email")
    if email and not _EMAIL_RE.match(email):
        errors.append("email must be a valid email address.")
    orcid = fields.get("orcid")
    if orcid and not _ORCID_RE.match(orcid):
        errors.append("orcid must look like 0000-0002-1825-0097.")
    scholar = fields.get("google_scholar")
    if scholar and not _URL_RE.match(scholar):
        errors.append("google_scholar must be an http(s) URL.")
    for key in ("admission_date", "expected_graduation"):
        value = fields.get(key)
        if value and not _DATE_RE.match(value):
            errors.append(f"{key} must be YYYY, YYYY-MM, or YYYY-MM-DD.")
    links = fields.get("links")
    if links:
        for group in links:
            if group not in LINK_GROUPS:
                errors.append(
                    f"Unknown link group: {group!r} (expected one of {', '.join(LINK_GROUPS)})."
                )


def validate_create_student_input(dto: CreateStudentInput) -> list[str]:
    errors: list[str] = []
    if not dto.name or not dto.name.strip():
        errors.append("Name must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if not dto.student_type:
        errors.append(f"student_type is required (one of: {', '.join(STUDENT_TYPES)}).")
    if not (dto.roll_number and dto.roll_number.strip()):
        errors.append("roll_number is required (the institution identity of a student).")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_common(
        errors,
        student_type=dto.student_type or None,
        semester=dto.semester,
        email=dto.email,
        orcid=dto.orcid,
        google_scholar=dto.google_scholar,
        admission_date=dto.admission_date,
        expected_graduation=dto.expected_graduation,
        links=dto.links,
    )
    return errors


def validate_update_student_input(dto: UpdateStudentInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.name is not None and not dto.name.strip():
        errors.append("Name must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_common(
        errors,
        student_type=dto.student_type,
        semester=dto.semester,
        email=dto.email,
        orcid=dto.orcid,
        google_scholar=dto.google_scholar,
        admission_date=dto.admission_date,
        expected_graduation=dto.expected_graduation,
        links=dto.links,
    )
    # A provided roll_number must not be blanked (identity protection).
    if dto.roll_number is not None and not dto.roll_number.strip():
        errors.append("roll_number must not be emptied (it identifies the student).")
    return errors


def validate_list_students_query(query: ListStudentsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.student_type is not None and query.student_type not in STUDENT_TYPES:
        errors.append(f"student_type must be one of: {', '.join(STUDENT_TYPES)}.")
    if query.semester is not None and not 1 <= int(query.semester) <= 12:
        errors.append("semester must be between 1 and 12.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    return errors


def assert_valid_create_student_input(dto: CreateStudentInput) -> None:
    errors = validate_create_student_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_student_input(dto: UpdateStudentInput) -> None:
    errors = validate_update_student_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_students_query(query: ListStudentsQuery) -> None:
    errors = validate_list_students_query(query)
    if errors:
        raise ValidationError("; ".join(errors))
