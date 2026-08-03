"""Validators for the Reports & Analytics boundary.

Mirrors ``validators/events.py``: pure functions raising the application-layer
``ValidationError`` (mapped to 422 at the interface); no framework imports.
"""
from __future__ import annotations

from datetime import date

from app.application.dtos.reports import (
    ALL_FILTER_KEYS,
    EXPORT_FORMATS,
    FILTER_KEYS_BY_KIND,
    REPORT_KINDS,
    ReportFilters,
)
from app.application.exceptions import ValidationError

MIN_YEAR = 1900
MAX_YEAR = 2200


def _clean(raw: str | None, name: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationError(f"{name} must be a string when provided")
    value = raw.strip()
    return value or None


def _assert_date(raw: str | None, name: str) -> str | None:
    value = _clean(raw, name)
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{name} must be an ISO date (YYYY-MM-DD)") from None
    # date.fromisoformat accepts e.g. "2026-1-1"; the contract is the canonical
    # zero-padded format (the whole platform's wire format).
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValidationError(f"{name} must be an ISO date (YYYY-MM-DD)")
    return value


def assert_valid_report_kind(kind: str) -> str:
    value = (kind or "").strip().lower()
    if value not in REPORT_KINDS:
        raise ValidationError(
            f"unknown report kind '{kind}' (expected one of {', '.join(REPORT_KINDS)})"
        )
    return value


def assert_valid_export_format(fmt: str) -> str:
    value = (fmt or "").strip().lower()
    if value not in EXPORT_FORMATS:
        raise ValidationError(
            f"unknown export format '{fmt}' (expected one of {', '.join(EXPORT_FORMATS)})"
        )
    return value


def assert_valid_filters(filters: ReportFilters, kind: str) -> ReportFilters:
    """Validate + normalise the PART 12 filters for a report kind.

    Filters the kind does not honour (``FILTER_KEYS_BY_KIND``) are dropped
    rather than rejected — the analytics lens ignores per-object pickers, and
    a URL copied between workspaces stays meaningful. The applied subset is
    recorded on the resulting ``ReportView.applied_filters``.
    """
    allowed = FILTER_KEYS_BY_KIND[kind]

    year = filters.year
    if year is not None:
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValidationError("year must be an integer")
        if year < MIN_YEAR or year > MAX_YEAR:
            raise ValidationError(f"year must be between {MIN_YEAR} and {MAX_YEAR}")

    date_from = _assert_date(filters.date_from, "date_from")
    date_to = _assert_date(filters.date_to, "date_to")
    if date_from and date_to and date_from > date_to:
        raise ValidationError("date_from must not be after date_to")

    values = {
        "year": year,
        "date_from": date_from,
        "date_to": date_to,
        "faculty_id": _clean(filters.faculty_id, "faculty_id"),
        "student_id": _clean(filters.student_id, "student_id"),
        "project_id": _clean(filters.project_id, "project_id"),
        "grant_id": _clean(filters.grant_id, "grant_id"),
        "department": _clean(filters.department, "department"),
        "event_id": _clean(filters.event_id, "event_id"),
        "committee_id": _clean(filters.committee_id, "committee_id"),
    }
    for key in ALL_FILTER_KEYS:
        if key not in allowed:
            values[key] = None
    return ReportFilters(**values)


def applied_filter_strings(filters: ReportFilters) -> dict[str, str]:
    """Human-readable record of the filters actually applied (workspace +
    export headers). Money-free dates/ids only — display strings."""
    out: dict[str, str] = {}
    if filters.year is not None:
        out["year"] = str(filters.year)
    if filters.date_from:
        out["date_from"] = filters.date_from
    if filters.date_to:
        out["date_to"] = filters.date_to
    for key in (
        "faculty_id", "student_id", "project_id", "grant_id", "department",
        "event_id", "committee_id",
    ):
        value = getattr(filters, key)
        if value:
            out[key] = value
    return out
