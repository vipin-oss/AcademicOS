"""Validators for the Settings & Preferences inputs.

Mirrors ``validators/productivity.py`` one-to-one: small ``assert_*``
helpers raising ``ValidationError`` (mapped to 422 by the routers), driven
by the ``SECTION_FIELD_SPECS`` catalogue from the DTO module — every
provided key must exist in its section's spec and match its declared type
and value rules.
"""
from __future__ import annotations

import re

from app.application.dtos.productivity import CALENDAR_SOURCE_CODES
from app.application.dtos.settings import (
    AI_LAYOUT_CODES,
    AI_REPORT_FORMAT_CODES,
    CALENDAR_VIEW_DEFAULT_CODES,
    DASHBOARD_VIEW_CODES,
    DATE_FORMAT_CODES,
    MODULE_CODES,
    PHOTO_MAX_BYTES,
    PHOTO_MIME_TYPES,
    PRIORITY_DEFAULT_CODES,
    REMINDER_DEFAULT_CODES,
    SEARCH_RECENT_LIMIT_MAX,
    SEARCH_RECENT_LIMIT_MIN,
    SEARCH_SCOPE_CODES,
    SECTION_ACADEMIC,
    SECTION_AI,
    SECTION_APPEARANCE,
    SECTION_CODES,
    SECTION_DASHBOARD,
    SECTION_FIELD_SPECS,
    SECTION_NOTIFICATIONS,
    SECTION_PROFILE,
    SECTION_SEARCH,
    THEMES,
    WIDGET_CODES,
    ImportSettingsInput,
    ResetSettingsInput,
    SectionUpdateInput,
    SetProfilePhotoInput,
)
from app.application.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LANDING_RE = re.compile(r"^/[A-Za-z0-9/_{}\-.]*$")
THEME_CODES = tuple(code for code, _ in THEMES)


def _err(message: str) -> None:
    raise ValidationError(message)


def _assert_known_section(section: str) -> None:
    if section not in SECTION_CODES:
        _err(f"section must be one of: {', '.join(SECTION_CODES)}.")


def _assert_str(value: object, field_name: str, max_len: int = 200) -> str:
    if not isinstance(value, str):
        _err(f"{field_name} must be a string.")
    trimmed = value.strip()
    if len(trimmed) > max_len:
        _err(f"{field_name} must be at most {max_len} characters.")
    return trimmed


def _assert_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        _err(f"{field_name} must be a boolean.")
    return value


def _assert_int(value: object, field_name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _err(f"{field_name} must be an integer.")
    if value < minimum or value > maximum:
        _err(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def _assert_choice(value: object, field_name: str, codes: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value.strip().lower() not in codes:
        _err(f"{field_name} must be one of: {', '.join(codes)}.")
    return value.strip().lower()


def _assert_str_list(value: object, field_name: str, codes: tuple[str, ...] | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _err(f"{field_name} must be a list of strings.")
    cleaned = [item.strip() for item in value if item.strip()]
    if codes is not None:
        for item in cleaned:
            if item not in codes:
                _err(f"{field_name} entries must be one of: {', '.join(codes)}.")
    return cleaned


def _assert_str_map(value: object, field_name: str, codes: tuple[str, ...] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _err(f"{field_name} must be an object with string keys.")
    if codes is not None:
        for key in value:
            if key not in codes:
                _err(f"{field_name} keys must be one of: {', '.join(codes)}.")
    return dict(value)


# ---------------------------------------------------------------------------
# Per-field rules beyond the spec type
# ---------------------------------------------------------------------------
def _validate_field(section: str, field_name: str, value: object, spec_type: str) -> object:
    if spec_type == "str":
        text = _assert_str(value, f"{section}.{field_name}", 1000 if field_name == "biography" else 200)
        if section == SECTION_PROFILE and field_name == "email" and text:
            if not _EMAIL_RE.match(text):
                _err("profile.email must be a valid email address.")
        if section == SECTION_APPEARANCE and field_name == "theme":
            text = _assert_choice(text, f"{section}.{field_name}", THEME_CODES)
        if section == SECTION_ACADEMIC and field_name == "date_format":
            text = _assert_choice(text, f"{section}.{field_name}", DATE_FORMAT_CODES)
        if section == SECTION_NOTIFICATIONS:
            if field_name == "reminder_default":
                text = _assert_choice(text, f"{section}.{field_name}", REMINDER_DEFAULT_CODES)
            if field_name == "priority_default":
                text = _assert_choice(text, f"{section}.{field_name}", PRIORITY_DEFAULT_CODES)
            if field_name == "calendar_default_view":
                text = _assert_choice(text, f"{section}.{field_name}", CALENDAR_VIEW_DEFAULT_CODES)
        if section == SECTION_DASHBOARD:
            if field_name == "default_view":
                text = _assert_choice(text, f"{section}.{field_name}", DASHBOARD_VIEW_CODES)
            if field_name == "default_landing_page":
                if not text.startswith("/"):
                    text = f"/{text}"
                if not _LANDING_RE.match(text):
                    _err("dashboard.default_landing_page must be an app route (starts with '/').")
        if section == SECTION_SEARCH and field_name == "default_scope":
            text = _assert_choice(text, f"{section}.{field_name}", SEARCH_SCOPE_CODES)
        if section == SECTION_AI:
            if field_name == "preferred_report_format":
                text = _assert_choice(text, f"{section}.{field_name}", AI_REPORT_FORMAT_CODES)
            if field_name == "preferred_dashboard_layout":
                text = _assert_choice(text, f"{section}.{field_name}", AI_LAYOUT_CODES)
        return text
    if spec_type == "bool":
        return _assert_bool(value, f"{section}.{field_name}")
    if spec_type == "int":
        if section == SECTION_SEARCH:
            return _assert_int(value, f"{section}.{field_name}", SEARCH_RECENT_LIMIT_MIN, SEARCH_RECENT_LIMIT_MAX)
        return _assert_int(value, f"{section}.{field_name}", 1, 200)
    if spec_type == "list":
        if section == SECTION_DASHBOARD:
            return _assert_str_list(value, f"{section}.{field_name}", MODULE_CODES)
        return _assert_str_list(value, f"{section}.{field_name}", CALENDAR_SOURCE_CODES)
    if spec_type == "map":
        mapping = _assert_str_map(value, f"{section}.{field_name}", WIDGET_CODES if section == SECTION_DASHBOARD else None)
        if section == SECTION_DASHBOARD:
            for key, flag in mapping.items():
                mapping[key] = _assert_bool(flag, f"{section}.{field_name}.{key}")
        return mapping
    _err(f"Unknown spec type for {section}.{field_name}.")
    return None


def assert_valid_section_patch(section: str, values: dict[str, object]) -> dict[str, object]:
    """Validate one section patch; returns the cleaned (typed) values."""
    _assert_known_section(section)
    specs = dict(SECTION_FIELD_SPECS[section])
    cleaned: dict[str, object] = {}
    for key, value in values.items():
        if key not in specs:
            _err(f"Unknown {section} preference: '{key}'.")
        cleaned[key] = _validate_field(section, key, value, specs[key][0])
    return cleaned


def assert_valid_update_section_input(data: SectionUpdateInput) -> None:
    assert_valid_section_patch(data.section, dict(data.values))


def assert_valid_import_input(data: ImportSettingsInput) -> None:
    if not isinstance(data.sections, dict):
        _err("sections must be an object keyed by section code.")
    for section, values in data.sections.items():
        _assert_known_section(section)
        if not isinstance(values, dict):
            _err(f"sections.{section} must be an object of preference values.")
        assert_valid_section_patch(section, dict(values))


def assert_valid_reset_input(data: ResetSettingsInput) -> None:
    if data.sections is None:
        return
    if not isinstance(data.sections, list) or any(not isinstance(item, str) for item in data.sections):
        _err("sections must be a list of section codes.")
    for section in data.sections:
        _assert_known_section(section)


def assert_valid_photo_input(data: SetProfilePhotoInput) -> None:
    if not data.file_name or not data.file_name.strip():
        _err("file name is required.")
    if data.mime_type not in PHOTO_MIME_TYPES:
        _err(f"profile photo must be one of: {', '.join(PHOTO_MIME_TYPES)}.")
    if not data.content:
        _err("photo content must not be empty.")
    if len(data.content) > PHOTO_MAX_BYTES:
        _err(f"profile photo must be at most {PHOTO_MAX_BYTES // 1_000_000} MB.")
