"""Wire <-> boundary mapping for the Committees API (mirrors faculty_mapper).

Translates request dictionaries into input DTOs and output DTOs into
response dictionaries; the frozen `uploaded_by` -> `created_by` rename
happens here and only here. Link groups ride under ``links`` on the wire
(PART 7), members ride under ``members`` (PART 2).
"""
from __future__ import annotations

from dataclasses import asdict

from app.application.dtos.committee import (
    COMMITTEE_LINK_GROUPS,
    ActionItemOutput,
    CommitteeOutput,
    CreateActionItemInput,
    CreateCommitteeInput,
    CreateMeetingInput,
    MeetingOutput,
    UpdateActionItemInput,
    UpdateCommitteeInput,
    UpdateMeetingInput,
)
from app.application.exceptions import ValidationError
from app.domain.value_objects.enums import ObjectStatus


def _str_list(value: object) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _int_or_none(value: object) -> int | None:
    """Wire ints tolerate "42" and reject garbage with a clean 422."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"progress must be an integer 0..100, got {value!r}.") from None


def _rows(value: object) -> list[dict]:
    return [item for item in (value or []) if isinstance(item, dict)]


def _link_group(body: dict, group: str) -> list[str]:
    links = body.get("links") or {}
    return _str_list(links.get(group))


def _normalise_member_rows(rows: list[dict]) -> list[dict]:
    """Keep only the member columns; tolerate extra keys (they are dropped)."""
    normalised = []
    for row in rows:
        entry = {
            "faculty_id": str(row.get("faculty_id") or "").strip(),
            "role": str(row.get("role") or "").strip().lower(),
        }
        if row.get("start_date"):
            entry["start_date"] = str(row["start_date"]).strip()
        if row.get("end_date"):
            entry["end_date"] = str(row["end_date"]).strip()
        if row.get("remarks"):
            entry["remarks"] = str(row["remarks"]).strip()
        normalised.append(entry)
    return normalised


# ---------------------------------------------------------------------------
# Committee inputs
# ---------------------------------------------------------------------------
def to_create_committee_input(*, body: dict) -> CreateCommitteeInput:
    return CreateCommitteeInput(
        name=str(body.get("name") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        committee_code=body.get("committee_code"),
        committee_type=body.get("committee_type"),
        department=body.get("department"),
        school=body.get("school"),
        description=body.get("description"),
        constitution_date=body.get("constitution_date"),
        expiry_date=body.get("expiry_date"),
        notes=body.get("notes"),
        tags=_str_list(body.get("tags")),
        members=_normalise_member_rows(_rows(body.get("members"))),
        projects=_link_group(body, "projects"),
        grants=_link_group(body, "grants"),
        students=_link_group(body, "students"),
        publications=_link_group(body, "publications"),
    )


def to_update_committee_input(*, body: dict) -> UpdateCommitteeInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateCommitteeInput(
        actor=str(body.get("uploaded_by") or "system"),
        name=present("name"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        committee_code=present("committee_code"),
        committee_type=present("committee_type"),
        department=present("department"),
        school=present("school"),
        description=present("description"),
        constitution_date=present("constitution_date"),
        expiry_date=present("expiry_date"),
        notes=present("notes"),
        tags=_str_list(body["tags"]) if "tags" in body else None,
        members=(
            _normalise_member_rows(_rows(body["members"])) if "members" in body else None
        ),
        projects=_link_group(body, "projects") if "links" in body else None,
        grants=_link_group(body, "grants") if "links" in body else None,
        students=_link_group(body, "students") if "links" in body else None,
        publications=_link_group(body, "publications") if "links" in body else None,
    )


# ---------------------------------------------------------------------------
# Meeting inputs
# ---------------------------------------------------------------------------
def to_create_meeting_input(*, committee_id: str, body: dict) -> CreateMeetingInput:
    return CreateMeetingInput(
        title=str(body.get("title") or ""),
        committee_id=committee_id,
        created_by=str(body.get("uploaded_by") or ""),
        meeting_number=body.get("meeting_number"),
        meeting_date=body.get("meeting_date"),
        venue=body.get("venue"),
        mode=body.get("mode"),
        agenda_items=_rows(body.get("agenda_items")),
        minutes=body.get("minutes"),
        attendance=_rows(body.get("attendance")),
        decisions=_str_list(body.get("decisions")),
        remarks=body.get("remarks"),
    )


def to_update_meeting_input(*, body: dict) -> UpdateMeetingInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateMeetingInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        meeting_number=present("meeting_number"),
        meeting_date=present("meeting_date"),
        venue=present("venue"),
        mode=present("mode"),
        agenda_items=_rows(body["agenda_items"]) if "agenda_items" in body else None,
        minutes=present("minutes"),
        attendance=_rows(body["attendance"]) if "attendance" in body else None,
        decisions=_str_list(body["decisions"]) if "decisions" in body else None,
        remarks=present("remarks"),
    )


# ---------------------------------------------------------------------------
# Action item inputs
# ---------------------------------------------------------------------------
def to_create_action_item_input(*, meeting_id: str, body: dict) -> CreateActionItemInput:
    return CreateActionItemInput(
        title=str(body.get("title") or ""),
        meeting_id=meeting_id,
        created_by=str(body.get("uploaded_by") or ""),
        assigned_to=body.get("assigned_to"),
        due_date=body.get("due_date"),
        priority=body.get("priority"),
        status=str(body.get("status") or "pending"),
        progress=_int_or_none(body.get("progress")) or 0,
        completion_date=body.get("completion_date"),
        remarks=body.get("remarks"),
    )


def to_update_action_item_input(*, body: dict) -> UpdateActionItemInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateActionItemInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        assigned_to=present("assigned_to"),
        due_date=present("due_date"),
        priority=present("priority"),
        status=present("status"),
        progress=_int_or_none(present("progress")),
        completion_date=present("completion_date"),
        remarks=present("remarks"),
    )


# ---------------------------------------------------------------------------
# Responses (uploaded_by renamed from created_by — frozen idiom)
# ---------------------------------------------------------------------------
def committee_response(out: CommitteeOutput) -> dict:
    return {
        "id": out.id,
        "name": out.name,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "committee_code": out.committee_code,
        "committee_type": out.committee_type,
        "department": out.department,
        "school": out.school,
        "description": out.description,
        "constitution_date": out.constitution_date,
        "expiry_date": out.expiry_date,
        "notes": out.notes,
        "tags": out.tags,
        "members": [asdict(member) for member in out.members],
        "meetings": [asdict(meeting) for meeting in out.meetings],
        "links": {group: out.links.get(group, []) for group in COMMITTEE_LINK_GROUPS},
        "stats": out.stats
        or {"meetings": 0, "pending_actions": 0, "completed_actions": 0},
        "metadata": out.metadata,
        "events": out.events,
    }


def meeting_response(out: MeetingOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "meeting_number": out.meeting_number,
        "meeting_date": out.meeting_date,
        "venue": out.venue,
        "mode": out.mode,
        "agenda_items": out.agenda_items,
        "minutes": out.minutes,
        "attendance": out.attendance,
        "decisions": out.decisions,
        "remarks": out.remarks,
        "committee": out.committee,
        "action_items": [action_item_response(item) for item in out.action_items],
        "stats": out.stats
        or {"agenda_items": 0, "pending_actions": 0, "completed_actions": 0},
        "metadata": out.metadata,
        "events": out.events,
    }


def action_item_response(out: ActionItemOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "assigned_to": out.assigned_to,
        "assigned_name": out.assigned_name,
        "due_date": out.due_date,
        "priority": out.priority,
        "progress": out.progress,
        "completion_date": out.completion_date,
        "remarks": out.remarks,
        "meeting": out.meeting,
        "committee": out.committee,
    }
