"""Presentation mapper for Settings & Preferences (mirrors productivity_mapper).

Body dicts (extra keys forbidden by the pydantic models) become module
inputs verbatim; outputs become plain dicts for the responses. No business
logic here — shaping/typing lives in the use-case helpers.
"""
from __future__ import annotations

from typing import Any

from app.application.dtos.settings import (
    ImportSettingsInput,
    ResetSettingsInput,
    SectionUpdateInput,
)

# Section path segment -> section code (the 8 updatable sections).
SECTION_SEGMENTS: dict[str, str] = {
    "profile": "profile",
    "appearance": "appearance",
    "academic": "academic",
    "notifications": "notifications",
    "dashboard": "dashboard",
    "search": "search",
    "privacy": "privacy",
    "ai": "ai",
}


def to_section_update_input(section: str, body: dict) -> SectionUpdateInput:
    values = {key: value for key, value in body.items() if key not in ("section", "updated_by") and value is not None}
    return SectionUpdateInput(
        section=section,
        values=values,
        updated_by=(body.get("updated_by") or "system"),
    )


def to_import_input(body: dict) -> ImportSettingsInput:
    raw = body.get("sections")
    if raw is None:
        # tolerate posting the bare sections map {"profile": {...}, ...}
        raw = {key: value for key, value in body.items() if key in SECTION_SEGMENTS.values()}
    if not isinstance(raw, dict):
        raw = {}
    return ImportSettingsInput(
        sections=raw,
        updated_by=(body.get("updated_by") or "system"),
    )


def to_reset_input(body: dict) -> ResetSettingsInput:
    return ResetSettingsInput(
        sections=body.get("sections"),
        updated_by=(body.get("updated_by") or "system"),
    )


def clean_json(value: Any) -> Any:
    """Shape outputs for JSON. Bytes (photo content) become ``None``;

    every declared key is kept (null when unset) so the document schema is
    stable for clients — ``None`` values are NOT dropped.
    """
    if isinstance(value, bytes):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [clean_json(item) for item in value]
    return value


def output_dict(out: Any) -> dict[str, Any]:
    from dataclasses import asdict, is_dataclass

    return clean_json(asdict(out) if is_dataclass(out) else out)
