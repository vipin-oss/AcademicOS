"""Validation helpers for the Committees & Meetings use cases.

Mirrors ``validators/faculty.py`` / ``validators/research.py`` one-to-one:
framework-free assertion functions raising ``ValidationError`` (mapped to 422
at the API boundary). Existence/type checks on linked Objects live in the use
cases (they need the repository); everything purely syntactic lives here.
"""
from __future__ import annotations

import re

from app.application.dtos.committee import (
    ACTION_PRIORITIES,
    ACTION_STATUSES,
    AGENDA_ITEM_STATUSES,
    AGENDA_PRIORITIES,
    ATTENDANCE_STATUSES,
    MEETING_MODES,
    MEMBER_ROLES,
    CreateActionItemInput,
    CreateCommitteeInput,
    CreateMeetingInput,
    UpdateActionItemInput,
    UpdateCommitteeInput,
    UpdateMeetingInput,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_committees import ListCommitteesQuery

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _err(message: str) -> None:
    raise ValidationError(message)


def assert_optional_date(value: str | None, field: str) -> None:
    """Date fields use the registry format YYYY-MM-DD (None allowed)."""
    if value is not None and value.strip() and not _DATE_RE.match(value.strip()):
        _err(f"{field} must be a date (YYYY-MM-DD).")


def assert_valid_members(members: list[dict]) -> None:
    """Member rows: {faculty_id, role, start_date?, end_date?, remarks?}."""
    for index, member in enumerate(members or [], start=1):
        if not isinstance(member, dict):
            _err(f"members[{index}] must be an object.")
        target = str(member.get("faculty_id") or "").strip()
        if not target:
            _err(f"members[{index}].faculty_id is required (the member's Object).")
        role = str(member.get("role") or "").strip().lower()
        if role not in MEMBER_ROLES:
            _err(
                f"members[{index}].role '{member.get('role')}' is not a valid role "
                f"({', '.join(MEMBER_ROLES)})."
            )
        member["role"] = role
        assert_optional_date(member.get("start_date"), f"members[{index}].start_date")
        assert_optional_date(member.get("end_date"), f"members[{index}].end_date")


def assert_valid_agenda_items(items: list[dict]) -> None:
    """Agenda item rows (PART 4): {title, priority?, presenter?, discussion?,
    decision?, status?, document_ids?}."""
    for index, item in enumerate(items or [], start=1):
        if not isinstance(item, dict):
            _err(f"agenda_items[{index}] must be an object.")
        if not str(item.get("title") or "").strip():
            _err(f"agenda_items[{index}].title is required.")
        priority = str(item.get("priority") or "").strip().lower()
        if priority and priority not in AGENDA_PRIORITIES:
            _err(
                f"agenda_items[{index}].priority '{item.get('priority')}' is not valid "
                f"({', '.join(AGENDA_PRIORITIES)})."
            )
        status = str(item.get("status") or "").strip().lower()
        if status and status not in AGENDA_ITEM_STATUSES:
            _err(
                f"agenda_items[{index}].status '{item.get('status')}' is not valid "
                f"({', '.join(AGENDA_ITEM_STATUSES)})."
            )
        document_ids = item.get("document_ids")
        if document_ids is not None and not isinstance(document_ids, list):
            _err(f"agenda_items[{index}].document_ids must be a list of document ids.")


def assert_valid_attendance(attendance: list[dict]) -> None:
    """Attendance rows: {object_id | name, status}."""
    for index, entry in enumerate(attendance or [], start=1):
        if not isinstance(entry, dict):
            _err(f"attendance[{index}] must be an object.")
        if not str(entry.get("object_id") or entry.get("name") or "").strip():
            _err(f"attendance[{index}] needs an object_id or a name.")
        status = str(entry.get("status") or "").strip().lower()
        if status not in ATTENDANCE_STATUSES:
            _err(
                f"attendance[{index}].status '{entry.get('status')}' is not valid "
                f"({', '.join(ATTENDANCE_STATUSES)})."
            )
        entry["status"] = status


def _assert_decisions(decisions: list[str]) -> None:
    for index, decision in enumerate(decisions or [], start=1):
        if not str(decision).strip():
            _err(f"decisions[{index}] must not be empty.")


def assert_valid_create_committee_input(data: CreateCommitteeInput) -> None:
    if not str(data.name or "").strip():
        _err("Committee name must not be empty.")
    if not str(data.created_by or "").strip():
        _err("created_by must not be empty (audit trail).")
    assert_optional_date(data.constitution_date, "constitution_date")
    assert_optional_date(data.expiry_date, "expiry_date")
    if (
        data.constitution_date
        and data.expiry_date
        and data.expiry_date.strip() < data.constitution_date.strip()
    ):
        _err("expiry_date must not be before the constitution date.")
    assert_valid_members(data.members)


def assert_valid_update_committee_input(data: UpdateCommitteeInput) -> None:
    if data.name is not None and not str(data.name).strip():
        _err("Committee name must not be empty.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    assert_optional_date(data.constitution_date, "constitution_date")
    assert_optional_date(data.expiry_date, "expiry_date")
    if data.members is not None:
        assert_valid_members(data.members)


def assert_valid_list_committees_query(query: ListCommitteesQuery) -> None:
    if query.page < 1:
        _err("page must be >= 1.")
    if query.page_size < 1 or query.page_size > 100:
        _err("page_size must be between 1 and 100.")
    if query.meeting_year is not None and not (1900 <= query.meeting_year <= 2200):
        _err("meeting_year must be a calendar year.")


def _assert_meeting_fields(
    meeting_number: str | None,
    meeting_date: str | None,
    mode: str | None,
    agenda_items: list[dict] | None,
    attendance: list[dict] | None,
    decisions: list[str] | None,
) -> None:
    assert_optional_date(meeting_date, "meeting_date")
    if mode is not None:
        normalised = str(mode).strip().lower()
        if normalised and normalised not in MEETING_MODES:
            _err(f"mode '{mode}' is not valid ({', '.join(MEETING_MODES)}).")
    if agenda_items is not None:
        assert_valid_agenda_items(agenda_items)
    if attendance is not None:
        assert_valid_attendance(attendance)
    if decisions is not None:
        _assert_decisions(decisions)
    if meeting_number is not None and not str(meeting_number).strip():
        _err("meeting_number must not be empty when provided.")


def assert_valid_create_meeting_input(data: CreateMeetingInput) -> None:
    if not str(data.title or "").strip():
        _err("Meeting title must not be empty.")
    if not str(data.created_by or "").strip():
        _err("created_by must not be empty (audit trail).")
    _assert_meeting_fields(
        data.meeting_number, data.meeting_date, data.mode,
        data.agenda_items, data.attendance, data.decisions,
    )


def assert_valid_update_meeting_input(data: UpdateMeetingInput) -> None:
    if data.title is not None and not str(data.title).strip():
        _err("Meeting title must not be empty.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    _assert_meeting_fields(
        data.meeting_number, data.meeting_date, data.mode,
        data.agenda_items, data.attendance, data.decisions,
    )


def _assert_action_fields(
    due_date: str | None,
    priority: str | None,
    status: str | None,
    progress: int | None,
    completion_date: str | None,
) -> None:
    assert_optional_date(due_date, "due_date")
    assert_optional_date(completion_date, "completion_date")
    if priority is not None:
        normalised = str(priority).strip().lower()
        if normalised and normalised not in ACTION_PRIORITIES:
            _err(f"priority '{priority}' is not valid ({', '.join(ACTION_PRIORITIES)}).")
    if status is not None:
        normalised = str(status).strip().lower()
        if normalised and normalised not in ACTION_STATUSES:
            _err(f"status '{status}' is not valid ({', '.join(ACTION_STATUSES)}).")
    if progress is not None and not (0 <= int(progress) <= 100):
        _err("progress must be between 0 and 100.")


def assert_valid_create_action_item_input(data: CreateActionItemInput) -> None:
    if not str(data.title or "").strip():
        _err("Action item title must not be empty.")
    if not str(data.created_by or "").strip():
        _err("created_by must not be empty (audit trail).")
    _assert_action_fields(
        data.due_date, data.priority, data.status, data.progress, data.completion_date
    )


def assert_valid_update_action_item_input(data: UpdateActionItemInput) -> None:
    if data.title is not None and not str(data.title).strip():
        _err("Action item title must not be empty.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    _assert_action_fields(
        data.due_date, data.priority, data.status, data.progress, data.completion_date
    )
