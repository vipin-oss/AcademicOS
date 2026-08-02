"""Input validation for the Research Projects & Grants use cases.

Mirrors ``validators/student.py``: boundary validation before the domain is
touched; raises the application-layer ``ValidationError``.
"""
from __future__ import annotations

import re

from app.application.dtos.research import (
    GRANT_LINK_GROUPS,
    INSTALLMENT_STATUSES,
    MILESTONE_STATUSES,
    PROJECT_LIFECYCLE_STATUSES,
    PROJECT_LINK_GROUPS,
    PROJECT_PRIORITIES,
    TEAM_GROUPS,
    CreateAgencyInput,
    CreateGrantInput,
    CreateProjectInput,
    ExpenditureInput,
    InstallmentInput,
    MilestoneInput,
    ProgressUpdateInput,
    UpdateAgencyInput,
    UpdateGrantInput,
    UpdateMilestoneInput,
    UpdateProjectInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_agencies import ListAgenciesQuery
from app.application.queries.list_grants import ListGrantsQuery
from app.application.queries.list_projects import ListProjectsQuery
from app.domain.value_objects.enums import ObjectStatus

_DATE_RE = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")
_FULL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https?://\S+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


def _check_link_groups(errors: list[str], links: dict | None, allowed: tuple[str, ...]) -> None:
    if links:
        for group in links:
            if group not in allowed:
                errors.append(
                    f"Unknown link group: {group!r} (expected one of {', '.join(allowed)})."
                )


def _check_team_groups(errors: list[str], team: dict | None) -> None:
    if team:
        for group in team:
            if group not in TEAM_GROUPS:
                errors.append(
                    f"Unknown team group: {group!r} (expected one of {', '.join(TEAM_GROUPS)})."
                )


def _check_dates(errors: list[str], **fields: str | None) -> None:
    for key, value in fields.items():
        if value is not None and value != "" and not _DATE_RE.match(str(value)):
            errors.append(f"{key} must be YYYY, YYYY-MM, or YYYY-MM-DD.")


def _check_amounts(errors: list[str], **fields: float | None) -> None:
    for key, value in fields.items():
        if value is None:
            continue
        try:
            if float(value) < 0:
                errors.append(f"{key} must not be negative.")
        except (TypeError, ValueError):
            errors.append(f"{key} must be a number.")


def _validate_project_common(errors: list[str], **fields) -> None:
    lifecycle = fields.get("lifecycle_status")
    if lifecycle is not None and lifecycle not in PROJECT_LIFECYCLE_STATUSES:
        errors.append(
            f"lifecycle_status must be one of: {', '.join(PROJECT_LIFECYCLE_STATUSES)}."
        )
    priority = fields.get("priority")
    if priority is not None and priority != "" and priority not in PROJECT_PRIORITIES:
        errors.append(f"priority must be one of: {', '.join(PROJECT_PRIORITIES)}.")
    _check_dates(
        errors, start_date=fields.get("start_date"), end_date=fields.get("end_date")
    )
    start, end = fields.get("start_date"), fields.get("end_date")
    if start and end and str(end) < str(start):
        errors.append("end_date must not be before start_date.")
    _check_amounts(
        errors,
        budget_approved=fields.get("budget_approved"),
        budget_utilized=fields.get("budget_utilized"),
    )
    _check_link_groups(errors, fields.get("links"), PROJECT_LINK_GROUPS)
    _check_team_groups(errors, fields.get("team"))


def validate_create_project_input(dto: CreateProjectInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Project title must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_project_common(
        errors,
        lifecycle_status=dto.lifecycle_status,
        priority=dto.priority,
        start_date=dto.start_date,
        end_date=dto.end_date,
        budget_approved=dto.budget_approved,
        budget_utilized=dto.budget_utilized,
        links=dto.links,
        team=dto.team,
    )
    return errors


def validate_update_project_input(dto: UpdateProjectInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Project title must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    if dto.project_code is not None and not dto.project_code.strip():
        errors.append("project_code must not be emptied (it identifies the project).")
    _validate_project_common(
        errors,
        lifecycle_status=dto.lifecycle_status,
        priority=dto.priority,
        start_date=dto.start_date,
        end_date=dto.end_date,
        budget_approved=dto.budget_approved,
        budget_utilized=dto.budget_utilized,
        links=dto.links,
        team=dto.team,
    )
    return errors


def validate_list_projects_query(query: ListProjectsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.status is not None and query.status not in PROJECT_LIFECYCLE_STATUSES:
        errors.append(
            f"status must be one of: {', '.join(PROJECT_LIFECYCLE_STATUSES)}."
        )
    if query.year is not None and not 1900 <= int(query.year) <= 2200:
        errors.append("year must be a plausible calendar year.")
    return errors


def _validate_grant_common(errors: list[str], **fields) -> None:
    _check_amounts(errors, amount=fields.get("amount"))
    _check_link_groups(errors, fields.get("links"), GRANT_LINK_GROUPS)


def validate_create_grant_input(dto: CreateGrantInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Grant title must not be empty.")
    if not dto.grant_number or not dto.grant_number.strip():
        errors.append("grant_number is required (the institution identity of a grant).")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_grant_common(errors, amount=dto.amount, links=dto.links)
    return errors


def validate_update_grant_input(dto: UpdateGrantInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Grant title must not be empty.")
    if dto.grant_number is not None and not dto.grant_number.strip():
        errors.append("grant_number must not be emptied (it identifies the grant).")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_grant_common(errors, amount=dto.amount, links=dto.links)
    return errors


def validate_list_grants_query(query: ListGrantsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    return errors


def _validate_agency_common(errors: list[str], **fields) -> None:
    website = fields.get("website")
    if website and not _URL_RE.match(website):
        errors.append("website must be an http(s) URL.")
    email = fields.get("contact_email")
    if email and not _EMAIL_RE.match(email):
        errors.append("contact_email must be a valid email address.")


def validate_create_agency_input(dto: CreateAgencyInput) -> list[str]:
    errors: list[str] = []
    if not dto.name or not dto.name.strip():
        errors.append("Agency name must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_agency_common(errors, website=dto.website, contact_email=dto.contact_email)
    return errors


def validate_update_agency_input(dto: UpdateAgencyInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.name is not None and not dto.name.strip():
        errors.append("Agency name must not be empty.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    _validate_agency_common(errors, website=dto.website, contact_email=dto.contact_email)
    return errors


def validate_list_agencies_query(query: ListAgenciesQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        errors.append("page_size must be between 1 and 100.")
    if query.status is not None and query.status not in {s.value for s in ObjectStatus}:
        errors.append("Invalid status filter.")
    return errors


def validate_milestone_input(dto: MilestoneInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Milestone title must not be empty.")
    if not dto.date or not _FULL_DATE_RE.match(str(dto.date)):
        errors.append("Milestone date must be YYYY-MM-DD.")
    if dto.status not in MILESTONE_STATUSES:
        errors.append(f"status must be one of: {', '.join(MILESTONE_STATUSES)}.")
    return errors


def validate_update_milestone_input(dto: UpdateMilestoneInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Milestone title must not be empty.")
    if dto.date is not None and not _FULL_DATE_RE.match(str(dto.date)):
        errors.append("Milestone date must be YYYY-MM-DD.")
    if dto.status is not None and dto.status not in MILESTONE_STATUSES:
        errors.append(f"status must be one of: {', '.join(MILESTONE_STATUSES)}.")
    return errors


def validate_progress_update_input(dto: ProgressUpdateInput) -> list[str]:
    errors: list[str] = []
    if not dto.date or not _FULL_DATE_RE.match(str(dto.date)):
        errors.append("Update date must be YYYY-MM-DD.")
    try:
        percent = float(dto.percent)
    except (TypeError, ValueError):
        errors.append("percent must be a number between 0 and 100.")
    else:
        if not 0.0 <= percent <= 100.0:
            errors.append("percent must be between 0 and 100.")
    if not dto.remark or not dto.remark.strip():
        errors.append("remark must not be empty (a progress update says something).")
    return errors


def validate_installment_input(dto: InstallmentInput) -> list[str]:
    errors: list[str] = []
    try:
        if int(dto.installment_no) < 1:
            errors.append("installment_no must be >= 1.")
    except (TypeError, ValueError):
        errors.append("installment_no must be a whole number >= 1.")
    if not dto.date or not _FULL_DATE_RE.match(str(dto.date)):
        errors.append("Installment date must be YYYY-MM-DD.")
    _check_amounts(errors, amount=dto.amount)
    if dto.amount is None:
        errors.append("amount is required for an installment.")
    if dto.status not in INSTALLMENT_STATUSES:
        errors.append(f"status must be one of: {', '.join(INSTALLMENT_STATUSES)}.")
    return errors


def validate_expenditure_input(dto: ExpenditureInput) -> list[str]:
    errors: list[str] = []
    if not dto.date or not _FULL_DATE_RE.match(str(dto.date)):
        errors.append("Expenditure date must be YYYY-MM-DD.")
    if not dto.head or not dto.head.strip():
        errors.append("head is required (e.g. Equipment, Consumables, Travel).")
    _check_amounts(errors, amount=dto.amount)
    if dto.amount is None:
        errors.append("amount is required for an expenditure.")
    return errors


def _assert(errors: list[str]) -> None:
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_create_project_input(dto: CreateProjectInput) -> None:
    _assert(validate_create_project_input(dto))


def assert_valid_update_project_input(dto: UpdateProjectInput) -> None:
    _assert(validate_update_project_input(dto))


def assert_valid_list_projects_query(query: ListProjectsQuery) -> None:
    _assert(validate_list_projects_query(query))


def assert_valid_create_grant_input(dto: CreateGrantInput) -> None:
    _assert(validate_create_grant_input(dto))


def assert_valid_update_grant_input(dto: UpdateGrantInput) -> None:
    _assert(validate_update_grant_input(dto))


def assert_valid_list_grants_query(query: ListGrantsQuery) -> None:
    _assert(validate_list_grants_query(query))


def assert_valid_create_agency_input(dto: CreateAgencyInput) -> None:
    _assert(validate_create_agency_input(dto))


def assert_valid_update_agency_input(dto: UpdateAgencyInput) -> None:
    _assert(validate_update_agency_input(dto))


def assert_valid_list_agencies_query(query: ListAgenciesQuery) -> None:
    _assert(validate_list_agencies_query(query))


def assert_valid_milestone_input(dto: MilestoneInput) -> None:
    _assert(validate_milestone_input(dto))


def assert_valid_update_milestone_input(dto: UpdateMilestoneInput) -> None:
    _assert(validate_update_milestone_input(dto))


def assert_valid_progress_update_input(dto: ProgressUpdateInput) -> None:
    _assert(validate_progress_update_input(dto))


def assert_valid_installment_input(dto: InstallmentInput) -> None:
    _assert(validate_installment_input(dto))


def assert_valid_expenditure_input(dto: ExpenditureInput) -> None:
    _assert(validate_expenditure_input(dto))
