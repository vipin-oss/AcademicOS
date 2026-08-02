"""Shared helpers for the Events & Academic Activities use cases.

Mirrors ``use_cases/finance/helpers.py`` one-to-one: section-row normalisers
(the ``_normalise_member_rows`` precedent), document/publication/speaker
resolution (the ``annotate_proposal_sections`` precedent), computed event
stats, and the PART 9 dashboard aggregation (computed read, no stored
counters — the finance PART 11 precedent).
"""
from __future__ import annotations

from uuid import uuid4

from app.application.dtos.events import (
    ATTENDEE_ROLES,
    EVENT_LINK_GROUPS,
    KEY_EVENT_STATUS,
    KEY_EVENT_TYPE,
    KEY_PARTICIPATION,
    KEY_PRESENTATIONS,
    KEY_SCHEDULE,
    KEY_SPEAKERS,
    ORGANIZER_ROLES,
    PARTICIPATION_ROW_KEYS,
    PRESENTATION_COUNT_RELATIONS,
    PRESENTATION_ROW_KEYS,
    REGISTRATION_KEYS,
    SCHEDULE_ROW_KEYS,
    SPEAKER_ROW_KEYS,
    SPEAKING_ROLES,
    UPCOMING_EVENT_STATUSES,
    EventOutput,
    parse_json_object_list,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType

SECTION_ROW_KEYS: dict[str, tuple[str, ...]] = {
    "participation": PARTICIPATION_ROW_KEYS,
    "speakers": SPEAKER_ROW_KEYS,
    "schedule": SCHEDULE_ROW_KEYS,
    "presentations": PRESENTATION_ROW_KEYS,
}

SECTION_META_KEY: dict[str, str] = {
    "participation": KEY_PARTICIPATION,
    "speakers": KEY_SPEAKERS,
    "schedule": KEY_SCHEDULE,
    "presentations": KEY_PRESENTATIONS,
}
SECTION_KEYS = tuple(SECTION_META_KEY.keys())


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


# ---------------------------------------------------------------------------
# Row normalisers (unknown keys dropped; strings trimmed; speaker row_ids
# minted when absent so schedule rows can reference a stable speaker — the
# finance vendor_id precedent, inside one aggregate). Numbers/strings remain
# wire strings — parse on read.
# ---------------------------------------------------------------------------
def normalise_section_rows(section: str, rows: list[dict]) -> list[dict]:
    whitelist = SECTION_ROW_KEYS[section]
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        clean = {key: row[key] for key in whitelist if key in row and row[key] not in (None,)}
        for key, value in list(clean.items()):
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    del clean[key]
                    continue
                clean[key] = value
        if "document_ids" in clean:
            clean["document_ids"] = [str(raw) for raw in (clean["document_ids"] or [])]
        if section == "speakers" and "name" in clean and "row_id" not in clean:
            clean["row_id"] = uuid4().hex[:12]
        out.append(clean)
    return out


def normalise_registration(registration: dict) -> dict[str, int]:
    """All four counters, missing/blank normalised to zero (PART 5)."""
    out = {key: 0 for key in REGISTRATION_KEYS}
    for key in REGISTRATION_KEYS:
        value = (registration or {}).get(key)
        if value in (None, ""):
            continue
        out[key] = int(value if isinstance(value, int) else str(value).strip())
    return out


def section_rows(meta: dict[str, str], key: str) -> list[dict]:
    return parse_json_object_list(meta.get(key))


# ---------------------------------------------------------------------------
# Resolution (documents, publications, schedule speakers)
# ---------------------------------------------------------------------------
def _resolve_titles(
    repository: ObjectRepository, ids: list[str], expected: ObjectType
) -> dict[str, str]:
    wanted = sorted({str(raw) for raw in ids if raw})
    if not wanted:
        return {}
    return {
        str(obj.id): obj.title
        for obj in repository.find_by_ids(wanted)
        if obj.object_type is expected
    }


def annotate_event_sections(repository: ObjectRepository, output: EventOutput) -> None:
    """In-place: certificate/photo/supporting refs, schedule speaker names
    and presentation titles on every section row (the finance
    ``annotate_proposal_sections`` precedent)."""
    document_ids = sorted(
        {
            str(raw)
            for row in output.participation + output.speakers
            for raw in (
                [row.get("certificate_document_id")]
                + [row.get("photo_document_id")]
                + list(row.get("document_ids") or [])
            )
            if raw
        }
    )
    publication_ids = [str(row.get("publication_id") or "") for row in output.presentations]

    doc_titles = _resolve_titles(repository, document_ids, ObjectType.DOCUMENT)
    publication_titles = _resolve_titles(repository, publication_ids, ObjectType.PUBLICATION)
    speaker_names = {
        str(row.get("row_id")): str(row.get("name"))
        for row in output.speakers
        if row.get("row_id") and row.get("name")
    }

    for row in output.participation:
        raw = str(row.get("certificate_document_id") or "")
        if raw in doc_titles:
            row["certificate"] = {"id": raw, "title": doc_titles[raw]}
    for row in output.speakers:
        raw = str(row.get("photo_document_id") or "")
        if raw in doc_titles:
            row["photo"] = {"id": raw, "title": doc_titles[raw]}
        if "document_ids" in row:
            row["supporting_documents"] = [
                {"id": doc_id, "title": title}
                for doc_id in row.get("document_ids") or []
                if (title := doc_titles.get(str(doc_id))) is not None
            ]
    for row in output.schedule:
        name = speaker_names.get(str(row.get("speaker_id") or ""))
        if name is not None:
            row["speaker_name"] = name
    for row in output.presentations:
        raw = str(row.get("publication_id") or "")
        if raw in publication_titles:
            row["publication_title"] = publication_titles[raw]


# ---------------------------------------------------------------------------
# Computed stats + one shared enrichment
# ---------------------------------------------------------------------------
def event_stats(meta: dict[str, str]) -> dict[str, int]:
    participation = section_rows(meta, KEY_PARTICIPATION)
    speakers = section_rows(meta, KEY_SPEAKERS)
    schedule = section_rows(meta, KEY_SCHEDULE)
    presentations = section_rows(meta, KEY_PRESENTATIONS)
    return {
        "participation": len(participation),
        "speakers": len(speakers),
        "sessions": len(schedule),
        "presentations": len(presentations),
        "certificates": sum(
            1 for row in participation if row.get("certificate_document_id")
        ),
    }


def enrich_event_output(
    repository: ObjectRepository, obj: UniversalObject, output: EventOutput
) -> None:
    """The one shared event enrichment (the ``enrich_proposal_output``
    precedent): resolved document/publication/speaker refs on every section
    row, normalised link-group keys, and the computed stats block."""
    meta = _meta(obj)
    output.links = {group: output.links.get(group, []) for group in EVENT_LINK_GROUPS}
    annotate_event_sections(repository, output)
    output.stats = event_stats(meta)


# ---------------------------------------------------------------------------
# Event collectors used by the dashboard / list use case
# ---------------------------------------------------------------------------
def all_events(repository: ObjectRepository) -> list[UniversalObject]:
    return repository.find_by_type(ObjectType.EVENT)


# ---------------------------------------------------------------------------
# PART 9 — Dashboard cards (computed read)
# ---------------------------------------------------------------------------
def events_dashboard(repository: ObjectRepository) -> dict[str, int]:
    upcoming = 0
    completed = 0
    organized = 0
    attended = 0
    certificates = 0
    presentations = 0
    invited_talks = 0
    for obj in all_events(repository):
        meta = _meta(obj)
        status = meta.get(KEY_EVENT_STATUS) or "planned"
        if status in UPCOMING_EVENT_STATUSES:
            upcoming += 1
        if status == "completed":
            completed += 1
        roles = {
            str(row.get("role"))
            for row in section_rows(meta, KEY_PARTICIPATION)
            if row.get("role")
        }
        if roles & set(ORGANIZER_ROLES):
            organized += 1
        if roles & set(ATTENDEE_ROLES):
            attended += 1
        certificates += sum(
            1
            for row in section_rows(meta, KEY_PARTICIPATION)
            if row.get("certificate_document_id")
        )
        presentations += sum(
            1
            for row in section_rows(meta, KEY_PRESENTATIONS)
            if (row.get("relation") or "") in PRESENTATION_COUNT_RELATIONS
        )
        if (meta.get(KEY_EVENT_TYPE) or "") == "invited_talk" and roles & set(
            SPEAKING_ROLES
        ):
            invited_talks += 1
    return {
        "upcoming_events": upcoming,
        "completed_events": completed,
        "events_organized": organized,
        "events_attended": attended,
        "certificates": certificates,
        "presentations": presentations,
        "invited_talks": invited_talks,
    }
