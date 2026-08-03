"""Shared helpers for Settings & Preferences use cases.

Mirrors ``use_cases/productivity/helpers.py``: the single place that knows
how the settings document object is resolved, how ``"<section>.<field>"``
metadata keys map to typed preference values, and how outputs are shaped.

Storage model (PART 8, "Local Preferences — no auth redesign"):
exactly one ``ObjectType.SETTINGS`` object with ``settings.scope = "user"``
holds every section. Absence of any metadata entry means *factory default*
(the ``SECTION_FIELD_SPECS`` defaults), so the object is created nearly
empty and resets can always re-materialise defaults.
"""
from __future__ import annotations

import json

from app.application.dtos.settings import (
    KEY_HAS_PHOTO,
    KEY_PHOTO_MIME,
    KEY_PHOTO_NAME,
    KEY_SETTINGS_SCOPE,
    SECTION_CODES,
    SECTION_FIELD_SPECS,
    SETTINGS_TITLE,
    SettingsDocumentOutput,
    SettingsSectionOutput,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


def field_key(section: str, field_name: str) -> str:
    return f"{section}.{field_name}"


def _meta(obj) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def _parse(spec_type: str, raw: str | None, default: object) -> object:
    """Typed read of one stored value (absent/empty raw -> default)."""
    if raw is None or raw == "":
        return default
    if spec_type == "bool":
        return raw.strip().lower() == "true"
    if spec_type == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    if spec_type in ("list", "map"):
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError):
            return default
        expected = list if spec_type == "list" else dict
        return loaded if isinstance(loaded, expected) else default
    return raw


def _serialize(spec_type: str, value: object) -> str:
    if spec_type == "bool":
        return "true" if value else "false"
    if spec_type == "int":
        return str(int(value))
    if spec_type in ("list", "map"):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def get_or_create_settings(repository: ObjectRepository) -> UniversalObject:
    """Resolve the singleton settings object, creating it on first touch."""
    for obj in repository.find_by_type(ObjectType.SETTINGS):
        if _meta(obj).get(KEY_SETTINGS_SCOPE) == "user":
            return obj
    obj = UniversalObject.create(
        object_type=ObjectType.SETTINGS,
        title=SETTINGS_TITLE,
        created_by="system",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                MetadataEntry(
                    KEY_SETTINGS_SCOPE, "user", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                ),
            )
        ),
    )
    repository.save(obj)
    obj.pop_domain_events()  # settings bootstrap is not business history
    return obj


def read_section(obj, section: str) -> dict[str, object]:
    meta = _meta(obj)
    values: dict[str, object] = {}
    for field_name, (spec_type, default) in SECTION_FIELD_SPECS[section]:
        values[field_name] = _parse(spec_type, meta.get(field_key(section, field_name)), default)
    return values


def read_document(obj) -> dict[str, dict[str, object]]:
    return {section: read_section(obj, section) for section in SECTION_CODES}


def write_fields(obj, section: str, values: dict[str, object]) -> None:
    """Write already-validated field values (verbatim merge semantics)."""
    specs = dict(SECTION_FIELD_SPECS[section])
    for field_name, value in values.items():
        spec_type = specs[field_name][0]
        obj.set_metadata(
            MetadataEntry(
                field_key(section, field_name),
                _serialize(spec_type, value),
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            )
        )


def write_defaults(obj, section: str) -> None:
    """Re-materialise every field of a section at its factory default."""
    for field_name, (spec_type, default) in SECTION_FIELD_SPECS[section]:
        obj.set_metadata(
            MetadataEntry(
                field_key(section, field_name),
                _serialize(spec_type, default),
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            )
        )


# ---------------------------------------------------------------- photo keys
def read_photo_meta(obj) -> tuple[bool, str | None, str | None]:
    meta = _meta(obj)
    has_photo = (meta.get(KEY_HAS_PHOTO) or "").strip().lower() == "true"
    return has_photo, meta.get(KEY_PHOTO_MIME) or None, meta.get(KEY_PHOTO_NAME) or None


def write_photo_meta(obj, mime_type: str, file_name: str) -> None:
    for key, value in ((KEY_HAS_PHOTO, "true"), (KEY_PHOTO_MIME, mime_type), (KEY_PHOTO_NAME, file_name)):
        obj.set_metadata(MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED))


def clear_photo_meta(obj) -> None:
    for key in (KEY_HAS_PHOTO, KEY_PHOTO_MIME, KEY_PHOTO_NAME):
        obj.set_metadata(MetadataEntry(key, "", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED))


# ---------------------------------------------------------------- outputs
def document_output(obj, photo_url: str | None = None) -> SettingsDocumentOutput:
    has_photo, _mime, name = read_photo_meta(obj)
    audit = getattr(obj, "audit", None)
    updated = (getattr(audit, "updated_at", None) or getattr(audit, "created_at", None)) if audit else None
    return SettingsDocumentOutput(
        sections=read_document(obj),
        has_photo=has_photo,
        photo_name=name if has_photo else None,
        photo_url=photo_url if has_photo else None,
        updated_at=updated.isoformat() if updated else None,
    )


def section_output(obj, section: str) -> SettingsSectionOutput:
    return SettingsSectionOutput(section=section, values=read_section(obj, section))
