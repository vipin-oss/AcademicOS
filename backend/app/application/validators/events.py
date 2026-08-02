"""Validators for the Events & Academic Activities inputs.

Mirrors ``validators/finance.py`` one-to-one: file-local regexes, small
``assert_*`` helpers raising ``ValidationError`` (mapped to 422 by the
routers), and per-input entry points called first thing in every use case.
"""
from __future__ import annotations

import re

from app.application.dtos.events import (
    EVENT_MODES,
    EVENT_PRIORITIES,
    EVENT_STATUSES,
    EVENT_TYPES,
    PARTICIPATION_ROLES,
    PARTICIPATION_ROW_KEYS,
    PRESENTATION_RELATIONS,
    PRESENTATION_ROW_KEYS,
    REGISTRATION_KEYS,
    SCHEDULE_ROW_KEYS,
    SPEAKER_ROW_KEYS,
    CreateEventInput,
    UpdateEventInput,
)
from app.application.exceptions import ValidationError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_YEAR_RE = re.compile(r"^\d{4}$")


def _err(message: str) -> None:
    raise ValidationError(message)


def assert_optional_date(value: str | None, field: str) -> None:
    if value not in (None, "") and not _DATE_RE.match(str(value).strip()):
        _err(f"{field} must be an ISO date (YYYY-MM-DD).")


def assert_optional_time(value: str | None, field: str) -> None:
    if value not in (None, "") and not _TIME_RE.match(str(value).strip()):
        _err(f"{field} must be a 24-hour time (HH:MM).")


def assert_optional_email(value: str | None, field: str = "email") -> None:
    if value not in (None, "") and not _EMAIL_RE.match(str(value).strip()):
        _err(f"{field} must be a valid email address.")


def assert_choice(value: str | None, choices: tuple[str, ...], field: str) -> None:
    if value not in (None, "") and str(value).strip() not in choices:
        _err(f"{field} must be one of: {', '.join(choices)}.")


def assert_date_order(start: str | None, end: str | None) -> None:
    """End date must not precede the start date (both ISO when present)."""
    if start in (None, "") or end in (None, ""):
        return
    if str(end).strip() < str(start).strip():
        _err("end_date must not be before start_date.")


def _assert_str_keys(row: dict, whitelist: tuple[str, ...], section: str, index: int) -> None:
    if not isinstance(row, dict):
        _err(f"{section} row {index} must be an object.")
        return
    unknown = [key for key in row if key not in whitelist]
    if unknown:
        _err(f"{section} row {index} carries unknown keys: {', '.join(sorted(unknown))}.")


def _assert_document_ids(row: dict, section: str, index: int, key: str = "document_ids") -> None:
    value = row.get(key)
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _err(f"{section} row {index} {key} must be a list of object ids.")


def _assert_optional_document_id(row: dict, section: str, index: int, key: str) -> None:
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        _err(f"{section} row {index} {key} must be an object id string.")


def assert_valid_participation(rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, PARTICIPATION_ROW_KEYS, "participation", index)
        if row.get("role") in (None, ""):
            _err(f"participation row {index} requires a role.")
        assert_choice(row.get("role"), PARTICIPATION_ROLES, f"participation row {index} role")
        _assert_optional_document_id(row, "participation", index, "certificate_document_id")


def assert_valid_speakers(rows: list[dict]) -> None:
    row_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, SPEAKER_ROW_KEYS, "speakers", index)
        if row.get("name") in (None, ""):
            _err(f"speakers row {index} requires a name.")
        row_id = (row.get("row_id") or "").strip()
        if row_id:
            if row_id in row_ids:
                _err(f"duplicate speaker row_id {row_id!r} within the event.")
            row_ids.add(row_id)
        assert_optional_email(row.get("email"), f"speakers row {index} email")
        _assert_optional_document_id(row, "speakers", index, "photo_document_id")
        _assert_document_ids(row, "speakers", index)


def assert_valid_schedule(rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, SCHEDULE_ROW_KEYS, "schedule", index)
        if row.get("title") in (None, ""):
            _err(f"schedule row {index} requires a session title.")
        assert_optional_date(row.get("session_date"), f"schedule row {index} session_date")
        assert_optional_time(row.get("start_time"), f"schedule row {index} start_time")
        assert_optional_time(row.get("end_time"), f"schedule row {index} end_time")
        start = (row.get("start_time") or "").strip()
        end = (row.get("end_time") or "").strip()
        if start and end and end < start:
            _err(f"schedule row {index} end_time must not be before start_time.")
        if row.get("speaker_id") is not None and not isinstance(row.get("speaker_id"), str):
            _err(f"schedule row {index} speaker_id must reference a speaker row id.")


def assert_valid_presentations(rows: list[dict]) -> None:
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, PRESENTATION_ROW_KEYS, "presentations", index)
        publication_id = (row.get("publication_id") or "").strip()
        if not publication_id:
            _err(f"presentations row {index} requires a publication.")
        if publication_id in seen:
            _err(f"duplicate publication {publication_id!r} within the presentations.")
        seen.add(publication_id)
        assert_choice(
            row.get("relation"), PRESENTATION_RELATIONS, f"presentations row {index} relation"
        )


def _registration_int(value, field: str) -> None:
    if isinstance(value, bool):
        _err(f"registration {field} must be a non-negative integer.")
    if isinstance(value, int):
        parsed: int | None = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        parsed = None
    if parsed is None or parsed < 0:
        _err(f"registration {field} must be a non-negative integer.")


def assert_valid_registration(registration: dict) -> None:
    if registration is None:
        return
    if not isinstance(registration, dict):
        _err(
            "registration must be an object (expected_participants/registered/"
            "present/certificates_issued)."
        )
    unknown = [key for key in registration if key not in REGISTRATION_KEYS]
    if unknown:
        _err(f"registration carries unknown keys: {', '.join(sorted(unknown))}.")
    for key, value in registration.items():
        if value is None:
            continue  # missing/blank counters normalise to zero on write
        _registration_int(value, key)


def _assert_event_core(
    *,
    event_type,
    mode,
    event_status,
    priority,
    start_date,
    end_date,
) -> None:
    assert_choice(event_type, EVENT_TYPES, "event_type")
    assert_choice(mode, EVENT_MODES, "mode")
    assert_choice(event_status, EVENT_STATUSES, "event_status")
    assert_choice(priority, EVENT_PRIORITIES, "priority")
    assert_optional_date(start_date, "start_date")
    assert_optional_date(end_date, "end_date")
    assert_date_order(start_date, end_date)


def assert_valid_create_event_input(data: CreateEventInput) -> None:
    if data.title in (None, "") or not str(data.title).strip():
        _err("title is required.")
    if data.created_by in (None, "") or not str(data.created_by).strip():
        _err("created_by is required.")
    _assert_event_core(
        event_type=data.event_type,
        mode=data.mode,
        event_status=data.event_status,
        priority=data.priority,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")
    assert_valid_participation(list(data.participation or []))
    assert_valid_speakers(list(data.speakers or []))
    assert_valid_schedule(list(data.schedule or []))
    assert_valid_registration(data.registration)
    assert_valid_presentations(list(data.presentations or []))


def assert_valid_update_event_input(data: UpdateEventInput) -> None:
    if data.title is not None and not str(data.title).strip():
        _err("title cannot be blank.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    _assert_event_core(
        event_type=data.event_type,
        mode=data.mode,
        event_status=data.event_status,
        priority=data.priority,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")
    if data.participation is not None:
        assert_valid_participation(list(data.participation))
    if data.speakers is not None:
        assert_valid_speakers(list(data.speakers))
    if data.schedule is not None:
        assert_valid_schedule(list(data.schedule))
    if data.registration is not None:
        assert_valid_registration(data.registration)
    if data.presentations is not None:
        assert_valid_presentations(list(data.presentations))


def assert_valid_list_query(page: int, page_size: int) -> None:
    if page < 1:
        _err("page must be >= 1.")
    if page_size < 1 or page_size > 100:
        _err("page_size must be between 1 and 100.")


def assert_optional_year(value: str | None) -> None:
    if value not in (None, "") and not _YEAR_RE.match(str(value).strip()):
        _err("year must be a 4-digit calendar year (e.g. 2026).")
