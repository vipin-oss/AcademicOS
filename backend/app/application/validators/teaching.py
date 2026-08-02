"""Input validation for teaching use cases (classes/assignments/submissions/attendance).

Mirrors ``validators/publication.py``: boundary validation before the domain
is touched; raises the application-layer ``ValidationError``.
"""
from __future__ import annotations

import re

from app.application.dtos.teaching import (
    ASSIGNMENT_TYPES,
    ATTENDANCE_STATES,
    CLASS_MODES,
    VISIBILITIES,
    WEEKDAYS,
    CreateAssignmentInput,
    CreateClassInput,
    UpdateAssignmentInput,
    UpdateClassInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_classes import ListClassesQuery
from app.domain.value_objects.enums import ObjectStatus

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DEADLINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ][0-2]\d:[0-5]\d(:[0-5]\d)?(Z|[+-][0-2]\d:?[0-5]\d)?)?$")

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


def _validate_schedule(errors: list[str], slots) -> None:
    for slot in slots or ():
        if slot.get("day") not in WEEKDAYS:
            errors.append(f"weekly_schedule day must be one of: {', '.join(WEEKDAYS)}.")
            break
        for key in ("start", "end"):
            if slot.get(key) and not _TIME_RE.match(str(slot[key])):
                errors.append(f"weekly_schedule {key} must be HH:MM (24h).")
                break


def _validate_class(errors: list[str], **fields) -> None:
    semester = fields.get("semester")
    if semester is not None:
        try:
            if not 1 <= int(semester) <= 12:
                errors.append("semester must be between 1 and 12.")
        except (TypeError, ValueError):
            errors.append("semester must be a number between 1 and 12.")
    credits = fields.get("credits")
    if credits is not None:
        try:
            if not 0 <= float(credits) <= 40:
                errors.append("credits must be between 0 and 40.")
        except (TypeError, ValueError):
            errors.append("credits must be a number.")
    mode = fields.get("class_mode")
    if mode is not None and mode not in CLASS_MODES:
        errors.append(f"class_mode must be one of: {', '.join(CLASS_MODES)}.")
    links = fields.get("links")
    if links:
        for group in links:
            if group not in ("teachers", "departments"):
                errors.append("Unknown class link group (expected teachers/departments).")
    _validate_schedule(errors, fields.get("weekly_schedule"))


def validate_create_class_input(dto: CreateClassInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Class title must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_class(
        errors,
        semester=dto.semester,
        credits=dto.credits,
        class_mode=dto.class_mode,
        weekly_schedule=dto.weekly_schedule,
        links=dto.links,
    )
    return errors


def validate_update_class_input(dto: UpdateClassInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Class title must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_class(
        errors,
        semester=dto.semester,
        credits=dto.credits,
        class_mode=dto.class_mode,
        weekly_schedule=dto.weekly_schedule,
        links=dto.links,
    )
    return errors


def validate_list_classes_query(query: ListClassesQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.semester is not None and not 1 <= int(query.semester) <= 12:
        errors.append("semester must be between 1 and 12.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    return errors


def _validate_assignment(errors: list[str], **fields) -> None:
    kind = fields.get("assignment_type")
    if kind is not None and kind not in ASSIGNMENT_TYPES:
        errors.append(f"assignment_type must be one of: {', '.join(ASSIGNMENT_TYPES)}.")
    visibility = fields.get("visibility")
    if visibility is not None and visibility not in VISIBILITIES:
        errors.append(f"visibility must be one of: {', '.join(VISIBILITIES)}.")
    max_marks = fields.get("max_marks")
    if max_marks is not None:
        try:
            if float(max_marks) < 0:
                errors.append("max_marks must not be negative.")
        except (TypeError, ValueError):
            errors.append("max_marks must be a number.")
    weightage = fields.get("weightage")
    if weightage is not None:
        try:
            if not 0 <= float(weightage) <= 100:
                errors.append("weightage must be a percentage between 0 and 100.")
        except (TypeError, ValueError):
            errors.append("weightage must be a number.")
    deadline = fields.get("deadline")
    if deadline and not _DEADLINE_RE.match(deadline):
        errors.append("deadline must be a date (YYYY-MM-DD) or ISO datetime.")
    rubric = fields.get("rubric")
    for criterion in rubric or ():
        if not str(criterion.get("criterion", "")).strip():
            errors.append("Every rubric criterion needs a name.")
            break
        try:
            if float(criterion.get("marks", 0) or 0) < 0:
                errors.append("Rubric marks must not be negative.")
                break
        except (TypeError, ValueError):
            errors.append("Rubric marks must be numbers.")
            break


def validate_create_assignment_input(dto: CreateAssignmentInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Assignment title must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_assignment(
        errors,
        assignment_type=dto.assignment_type,
        visibility=dto.visibility,
        max_marks=dto.max_marks,
        weightage=dto.weightage,
        deadline=dto.deadline,
        rubric=dto.rubric,
    )
    return errors


def validate_update_assignment_input(dto: UpdateAssignmentInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Assignment title must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_assignment(
        errors,
        assignment_type=dto.assignment_type,
        visibility=dto.visibility,
        max_marks=dto.max_marks,
        weightage=dto.weightage,
        deadline=dto.deadline,
        rubric=dto.rubric,
    )
    return errors


def validate_marks_value(marks, max_marks) -> list[str]:
    """Grade boundary: non-negative number, <= the assignment maximum."""
    errors: list[str] = []
    try:
        value = float(marks)
    except (TypeError, ValueError):
        return ["marks must be a number."]
    if value < 0:
        errors.append("marks must not be negative.")
    if max_marks is not None and value > float(max_marks):
        errors.append(f"marks must not exceed the assignment maximum ({max_marks}).")
    return errors


def validate_attendance_records(records: dict) -> list[str]:
    errors: list[str] = []
    if not records:
        errors.append("records must map student ids to an attendance state.")
        return errors
    for state in records.values():
        if state not in ATTENDANCE_STATES:
            errors.append(
                f"attendance state must be one of: {', '.join(ATTENDANCE_STATES)}."
            )
            break
    return errors


def validate_session_date(value: str | None) -> list[str]:
    if not value or not _DATE_RE.match(value.strip()):
        return ["session_date must be YYYY-MM-DD."]
    return []


def assert_valid_create_class_input(dto: CreateClassInput) -> None:
    errors = validate_create_class_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_class_input(dto: UpdateClassInput) -> None:
    errors = validate_update_class_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_classes_query(query: ListClassesQuery) -> None:
    errors = validate_list_classes_query(query)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_create_assignment_input(dto: CreateAssignmentInput) -> None:
    errors = validate_create_assignment_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_assignment_input(dto: UpdateAssignmentInput) -> None:
    errors = validate_update_assignment_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))
