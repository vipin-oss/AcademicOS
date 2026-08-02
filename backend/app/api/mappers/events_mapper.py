"""Wire <-> boundary mapping for the Events & Academic Activities API.

Mirrors ``finance_mapper`` one-to-one: request dictionaries become input
DTOs and output DTOs become response dictionaries; the frozen
`uploaded_by` -> `created_by` rename happens here and only here. Link groups
ride under ``links``; the four section lists and the ``registration`` counter
block ride as top-level payloads (whitelisted on the boundary, extra keys
dropped there).
"""
from __future__ import annotations

from app.application.dtos.events import (
    EVENT_LINK_GROUPS,
    CreateEventInput,
    EventOutput,
    UpdateEventInput,
)
from app.domain.value_objects.enums import ObjectStatus


def _str_list(value: object) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _rows(value: object) -> list[dict]:
    return [item for item in (value or []) if isinstance(item, dict)]


def _link_group(body: dict, group: str) -> list[str]:
    links = body.get("links") or {}
    return _str_list(links.get(group))


def _registration(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Event inputs
# ---------------------------------------------------------------------------
def to_create_event_input(*, body: dict) -> CreateEventInput:
    return CreateEventInput(
        title=str(body.get("title") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "active")),
        event_code=body.get("event_code"),
        event_type=str(body.get("event_type") or "custom"),
        organizer=body.get("organizer"),
        co_organizer=body.get("co_organizer"),
        venue=body.get("venue"),
        mode=body.get("mode"),
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        department=body.get("department"),
        school=body.get("school"),
        description=body.get("description"),
        objectives=body.get("objectives"),
        outcome=body.get("outcome"),
        event_status=str(body.get("event_status") or "planned"),
        priority=body.get("priority"),
        notes=body.get("notes"),
        tags=_str_list(body.get("tags")),
        participation=_rows(body.get("participation")),
        speakers=_rows(body.get("speakers")),
        schedule=_rows(body.get("schedule")),
        registration=_registration(body.get("registration")),
        presentations=_rows(body.get("presentations")),
        faculty=_link_group(body, "faculty"),
        students=_link_group(body, "students"),
        projects=_link_group(body, "projects"),
        grants=_link_group(body, "grants"),
        committees=_link_group(body, "committees"),
    )


def to_update_event_input(*, body: dict) -> UpdateEventInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateEventInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        event_code=present("event_code"),
        event_type=present("event_type"),
        organizer=present("organizer"),
        co_organizer=present("co_organizer"),
        venue=present("venue"),
        mode=present("mode"),
        start_date=present("start_date"),
        end_date=present("end_date"),
        department=present("department"),
        school=present("school"),
        description=present("description"),
        objectives=present("objectives"),
        outcome=present("outcome"),
        event_status=present("event_status"),
        priority=present("priority"),
        notes=present("notes"),
        tags=_str_list(body["tags"]) if "tags" in body else None,
        participation=_rows(body["participation"]) if "participation" in body else None,
        speakers=_rows(body["speakers"]) if "speakers" in body else None,
        schedule=_rows(body["schedule"]) if "schedule" in body else None,
        registration=_registration(body["registration"]) if "registration" in body else None,
        presentations=_rows(body["presentations"]) if "presentations" in body else None,
        faculty=_link_group(body, "faculty") if "links" in body else None,
        students=_link_group(body, "students") if "links" in body else None,
        projects=_link_group(body, "projects") if "links" in body else None,
        grants=_link_group(body, "grants") if "links" in body else None,
        committees=_link_group(body, "committees") if "links" in body else None,
    )


# ---------------------------------------------------------------------------
# Responses (uploaded_by renamed from created_by — frozen idiom)
# ---------------------------------------------------------------------------
def event_response(out: EventOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "event_code": out.event_code,
        "event_type": out.event_type,
        "organizer": out.organizer,
        "co_organizer": out.co_organizer,
        "venue": out.venue,
        "mode": out.mode,
        "start_date": out.start_date,
        "end_date": out.end_date,
        "department": out.department,
        "school": out.school,
        "description": out.description,
        "objectives": out.objectives,
        "outcome": out.outcome,
        "event_status": out.event_status,
        "priority": out.priority,
        "notes": out.notes,
        "tags": out.tags,
        "participation": out.participation,
        "speakers": out.speakers,
        "schedule": out.schedule,
        "registration": out.registration,
        "presentations": out.presentations,
        "links": {group: out.links.get(group, []) for group in EVENT_LINK_GROUPS},
        "stats": out.stats
        or {
            "participation": 0,
            "speakers": 0,
            "sessions": 0,
            "presentations": 0,
            "certificates": 0,
        },
        "metadata": out.metadata,
        "events": out.events,
    }
