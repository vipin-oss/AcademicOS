"""Validators for the Productivity Hub inputs.

Mirrors ``validators/events.py`` one-to-one: file-local regexes, small
``assert_*`` helpers raising ``ValidationError`` (mapped to 422 by the
routers), and per-input entry points called first thing in every use case.
"""
from __future__ import annotations

import re

from app.application.dtos.productivity import (
    NOTIFICATION_CATEGORIES,
    NOTIFICATION_PRIORITIES,
    TASK_CATEGORIES,
    TASK_PRIORITIES,
    CreateEntryInput,
    CreateNotificationInput,
    CreateTaskInput,
    UpdateEntryInput,
    UpdateNotificationInput,
    UpdateTaskInput,
)
from app.application.exceptions import ValidationError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_YEAR_WINDOW_RE = re.compile(r"^(19|20|21|22)\d{2}$")

TASK_PRIORITY_CODES = tuple(code for code, _ in TASK_PRIORITIES)
TASK_CATEGORY_CODES = tuple(code for code, _ in TASK_CATEGORIES)
NOTIFICATION_PRIORITY_CODES = tuple(code for code, _ in NOTIFICATION_PRIORITIES)
NOTIFICATION_CATEGORY_CODES = tuple(code for code, _ in NOTIFICATION_CATEGORIES)


def _err(message: str) -> None:
    raise ValidationError(message)


def assert_optional_date(value: str | None, field: str) -> None:
    if value not in (None, "") and not _DATE_RE.match(str(value).strip()):
        _err(f"{field} must be an ISO date (YYYY-MM-DD).")


def assert_optional_time(value: str | None, field: str) -> None:
    if value not in (None, "") and not _TIME_RE.match(str(value).strip()):
        _err(f"{field} must be a 24-hour time (HH:MM).")


def assert_optional_priority(value: str | None, codes: tuple[str, ...] = TASK_PRIORITY_CODES) -> None:
    if value not in (None, "") and str(value).strip().lower() not in codes:
        _err(f"priority must be one of: {', '.join(codes)}.")


def assert_optional_category(value: str | None, codes: tuple[str, ...] = TASK_CATEGORY_CODES) -> None:
    if value not in (None, "") and str(value).strip().lower() not in codes:
        _err(f"category must be one of: {', '.join(codes)}.")


def assert_optional_tags(value: list[str] | None) -> None:
    if value is None:
        return
    if not isinstance(value, list) or any(not str(tag).strip() for tag in value):
        _err("tags must be a list of non-empty strings.")


def _assert_title(title: str | None) -> None:
    if title is None or not title.strip():
        _err("title is required.")
    if len(title.strip()) > 200:
        _err("title must be at most 200 characters.")


def _assert_actor(actor: str | None) -> None:
    if actor is None or not actor.strip():
        _err("uploaded_by is required.")


def _assert_date_window(start: str | None, end: str | None) -> None:
    if start and end and str(start) > str(end):
        _err("start_date must not be after end_date/due_date.")


# ---------------------------------------------------------------------------
# Tasks (PART 3)
# ---------------------------------------------------------------------------
def _assert_task_fields(data: CreateTaskInput | UpdateTaskInput) -> None:
    assert_optional_date(data.start_date, "start_date")
    assert_optional_date(data.due_date, "due_date")
    assert_optional_date(data.reminder, "reminder")
    assert_optional_priority(data.priority)
    assert_optional_category(data.category)
    assert_optional_tags(data.tags)
    start = data.start_date if data.start_date else None
    end = data.due_date if data.due_date else None
    _assert_date_window(start, end)


def assert_valid_create_task_input(data: CreateTaskInput) -> None:
    _assert_title(data.title)
    _assert_actor(data.uploaded_by)
    _assert_task_fields(data)


def assert_valid_update_task_input(data: UpdateTaskInput) -> None:
    if data.title is not None and not data.title.strip():
        _err("title must not be empty.")
    _assert_task_fields(data)


# ---------------------------------------------------------------------------
# Calendar entries (PART 2 tail)
# ---------------------------------------------------------------------------
def _assert_entry_fields(data: CreateEntryInput | UpdateEntryInput) -> None:
    assert_optional_date(data.start_date, "start_date")
    assert_optional_date(data.end_date, "end_date")
    assert_optional_time(data.start_time, "start_time")
    assert_optional_time(data.end_time, "end_time")
    assert_optional_category(data.category)
    assert_optional_tags(data.tags)
    if data.start_time and data.end_time and str(data.start_time) > str(data.end_time):
        _err("start_time must not be after end_time.")
    _assert_date_window(
        data.start_date if data.start_date else None,
        data.end_date if data.end_date else None,
    )


def assert_valid_create_entry_input(data: CreateEntryInput) -> None:
    _assert_title(data.title)
    _assert_actor(data.uploaded_by)
    if not data.start_date or not str(data.start_date).strip():
        _err("start_date is required.")
    _assert_entry_fields(data)


def assert_valid_update_entry_input(data: UpdateEntryInput) -> None:
    if data.title is not None and not data.title.strip():
        _err("title must not be empty.")
    _assert_entry_fields(data)


# ---------------------------------------------------------------------------
# Notifications (PART 4)
# ---------------------------------------------------------------------------
def assert_valid_create_notification_input(data: CreateNotificationInput) -> None:
    _assert_title(data.title)
    if len(data.title.strip()) > 300:
        _err("title must be at most 300 characters.")
    assert_optional_priority(data.priority, NOTIFICATION_PRIORITY_CODES)
    assert_optional_category(data.category, NOTIFICATION_CATEGORY_CODES)


def assert_valid_update_notification_input(data: UpdateNotificationInput) -> None:
    if data.title is not None and not data.title.strip():
        _err("title must not be empty.")
    if data.snoozed_until not in (None, ""):
        assert_optional_date(data.snoozed_until, "snoozed_until")


# ---------------------------------------------------------------------------
# Feed / search window guards
# ---------------------------------------------------------------------------
def assert_calendar_window(date_from: str, date_to: str) -> None:
    assert_optional_date(date_from, "date_from")
    assert_optional_date(date_to, "date_to")
    if not date_from or not date_to:
        _err("date_from and date_to are required.")
    if date_from > date_to:
        _err("date_from must not be after date_to.")
    year_from, year_to = int(date_from[:4]), int(date_to[:4])
    if year_to - year_from > 2:
        _err("calendar windows may span at most 3 years.")


def assert_search_window(date_from: str | None, date_to: str | None) -> None:
    assert_optional_date(date_from, "date_from")
    assert_optional_date(date_to, "date_to")
    if date_from and date_to and date_from > date_to:
        _err("date_from must not be after date_to.")


def assert_optional_year(value: str | None) -> None:
    if value not in (None, "") and not _YEAR_WINDOW_RE.match(str(value).strip()):
        _err("year must be a 4-digit year between 1900 and 2299.")
