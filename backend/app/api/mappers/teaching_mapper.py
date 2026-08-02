"""Pure mapping between Teaching API shapes and Application DTOs.

Mirrors ``publication_mapper.py`` / ``student_mapper.py``: framework-free so
it stays unit-testable without FastAPI/Pydantic/SQLAlchemy. The computed
aggregates (roster, grid, attendance summary, gradebook, report, dashboard)
are plain dataclasses and serialise via ``dataclasses.asdict`` — they carry
no enums or value objects by construction.
"""
from __future__ import annotations

import dataclasses

from app.application.dtos.teaching import (
    CLASS_GROUP_TO_KIND,
    CLASS_LINK_GROUPS,
    CreateAssignmentInput,
    CreateClassInput,
    UpdateAssignmentInput,
    UpdateClassInput,
)
from app.domain.value_objects.enums import ObjectStatus
from app.domain.value_objects.object_id import ObjectId


def _payload(obj) -> dict:
    """Serialise a DTO dataclass tree into plain JSON-safe structures."""
    return dataclasses.asdict(obj)


# ----------------------------------------------------------------------- links
def parse_class_links_field(raw: dict | None) -> dict[str, tuple[ObjectId, ...]] | None:
    """Parse {teachers|departments: [object_id, ...]} into typed tuples."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"links must be an object of {{{', '.join(CLASS_LINK_GROUPS)}: [ids]}}."
        )
    links: dict[str, tuple[ObjectId, ...]] = {}
    for group, ids in raw.items():
        if group not in CLASS_GROUP_TO_KIND:
            raise ValueError(
                f"Unknown link group: {group!r} "
                f"(expected one of {', '.join(CLASS_LINK_GROUPS)})."
            )
        if not isinstance(ids, list):
            raise ValueError(f"links.{group} must be an array of Object ids.")
        links[group] = tuple(ObjectId.parse(str(oid)) for oid in ids)
    return links


def _as_dicts(raw: list | None, name: str) -> tuple[dict, ...]:
    """Weekly schedule / rubric payloads must be arrays of objects."""
    out = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            raise ValueError(f"{name} entries must be objects.")
        out.append(dict(entry))
    return tuple(out)


# ----------------------------------------------------------------------- class
def to_create_class_input(*, body: dict) -> CreateClassInput:
    """Convert the JSON create body into the Application ``CreateClassInput``."""
    return CreateClassInput(
        title=str(body.get("title") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        course_code=body.get("course_code"),
        programme=body.get("programme"),
        semester=body.get("semester"),
        section=body.get("section"),
        session=body.get("session"),
        credits=body.get("credits"),
        weekly_schedule=_as_dicts(body.get("weekly_schedule"), "weekly_schedule"),
        room=body.get("room"),
        class_mode=body.get("class_mode"),
        notes=body.get("notes"),
        tags=tuple(str(t) for t in (body.get("tags") or [])),
        status=ObjectStatus(body.get("status", "draft")),
        links=parse_class_links_field(body.get("links")),
        students=tuple(
            ObjectId.parse(str(oid)) for oid in (body.get("students") or [])
        ),
    )


def to_update_class_input(*, body: dict) -> UpdateClassInput:
    """Convert the JSON PUT/PATCH body (frozen merge contract)."""
    def present(name: str):
        return body[name] if name in body else None

    return UpdateClassInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        course_code=present("course_code"),
        programme=present("programme"),
        semester=present("semester"),
        section=present("section"),
        session=present("session"),
        credits=present("credits"),
        weekly_schedule=(
            _as_dicts(body["weekly_schedule"], "weekly_schedule")
            if "weekly_schedule" in body
            else None
        ),
        room=present("room"),
        class_mode=present("class_mode"),
        notes=present("notes"),
        tags=(tuple(str(t) for t in body["tags"]) if "tags" in body else None),
        links=parse_class_links_field(body["links"]) if "links" in body else None,
    )


def class_to_response(out) -> dict:
    """Project a ``ClassOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "course_code": out.course_code,
        "programme": out.programme,
        "semester": out.semester,
        "section": out.section,
        "session": out.session,
        "credits": out.credits,
        "weekly_schedule": out.weekly_schedule,
        "room": out.room,
        "class_mode": out.class_mode,
        "notes": out.notes,
        "tags": out.tags,
        "student_count": out.student_count,
        "links": out.links,
        "metadata": out.metadata,
        "events": out.events,
    }


# ------------------------------------------------------------------ assignment
def to_create_assignment_input(*, body: dict, class_id: ObjectId | None = None) -> CreateAssignmentInput:
    """Convert the JSON create body into ``CreateAssignmentInput``.

    ``class_id`` may come from the path (class-scoped POST) or the body
    (top-level POST); the path wins when both are present.
    """
    raw_class = class_id or ObjectId.parse(str(body.get("class_id") or ""))
    return CreateAssignmentInput(
        title=str(body.get("title") or ""),
        class_id=raw_class,
        created_by=str(body.get("uploaded_by") or ""),
        assignment_type=str(body.get("assignment_type") or "assignment"),
        description=body.get("description"),
        instructions=body.get("instructions"),
        max_marks=body.get("max_marks"),
        deadline=body.get("deadline"),
        late_allowed=bool(body.get("late_allowed", False)),
        rubric=_as_dicts(body.get("rubric"), "rubric"),
        visibility=str(body.get("visibility") or "visible"),
        weightage=body.get("weightage"),
        status=ObjectStatus(body.get("status", "draft")),
    )


def to_update_assignment_input(*, body: dict) -> UpdateAssignmentInput:
    """Convert the JSON PUT/PATCH body (frozen merge contract)."""
    def present(name: str):
        return body[name] if name in body else None

    return UpdateAssignmentInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        assignment_type=present("assignment_type"),
        description=present("description"),
        instructions=present("instructions"),
        max_marks=present("max_marks"),
        deadline=present("deadline"),
        late_allowed=present("late_allowed"),
        rubric=(_as_dicts(body["rubric"], "rubric") if "rubric" in body else None),
        visibility=present("visibility"),
        weightage=present("weightage"),
    )


def assignment_to_response(out, *, attachment_url: str | None = None) -> dict:
    """Project an ``AssignmentOutput`` into a JSON-serialisable dict."""
    payload = _payload(out)
    payload["uploaded_by"] = out.created_by
    payload["attachment_url"] = attachment_url or out.attachment_url
    payload.pop("created_by", None)
    return payload


# ------------------------------------------------------------------ submission
def submission_to_response(out, *, file_url: str | None = None) -> dict:
    """Project a ``SubmissionOutput`` into a JSON-serialisable dict."""
    payload = _payload(out)
    payload["file_url"] = file_url or out.file_url
    return payload


# ------------------------------------------------------ computed aggregates
def grid_to_response(grid) -> dict:
    return _payload(grid)


def roster_to_response(entries) -> list[dict]:
    return [_payload(e) for e in entries]


def enrollment_result_to_response(result) -> dict:
    return _payload(result)


def attendance_session_to_response(out) -> dict:
    return _payload(out)


def attendance_summary_to_response(summary) -> dict:
    return _payload(summary)


def gradebook_to_response(gradebook) -> dict:
    return _payload(gradebook)


def gradebook_csv_parts(gradebook) -> tuple[list[dict], list[dict]]:
    """(assignment headers, row dicts) shaped for ``export_gradebook_csv``."""
    payload = _payload(gradebook)
    return payload["assignments"], payload["rows"]


def report_to_response(report) -> dict:
    payload = _payload(report)
    payload["class_info"] = class_to_response(report.class_info)
    return payload


def dashboard_to_response(dashboard) -> dict:
    payload = _payload(dashboard)
    payload["classes"] = [class_to_response(c) for c in dashboard.classes]
    return payload


def marks_import_to_response(result) -> dict:
    return _payload(result)


def attendance_import_to_response(result) -> dict:
    return _payload(result)
