"""Shared helpers for the Committees & Meetings use cases.

Mirrors ``use_cases/research/helpers.py`` one-to-one: child collectors over
``BELONGS_TO`` edges, members/leadership resolution for the filters
the ``_agency_names`` reverse-scan precedent, and the small output shapers.
"""
from __future__ import annotations

from app.application.dtos.committee import (
    KEY_ACTION_STATUS,
    KEY_ASSIGNED_NAME,
    KEY_ASSIGNED_TO,
    KEY_COMPLETION_DATE,
    KEY_DUE_DATE,
    KEY_MEETING_DATE,
    KEY_MEETING_NUMBER,
    KEY_MEMBERS,
    KEY_MODE,
    KEY_PRIORITY,
    KEY_PROGRESS,
    KEY_REMARKS,
    KEY_VENUE,
    ActionItemOutput,
    MeetingSummaryOutput,
    MemberView,
    link_dict,
    parse_json_object_list,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


# ---------------------------------------------------------------------------
# Child collectors (the milestones_of_project doctrine)
# ---------------------------------------------------------------------------
def meetings_of_committee(
    repository: ObjectRepository, committee_id: str
) -> list[UniversalObject]:
    """Every meeting BELONGS_TO this committee (date-desc, number tie-break)."""
    meetings = [
        obj
        for obj in repository.find_by_type(ObjectType.MEETING)
        if any(
            rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) == committee_id
            for rel in obj.relationships
        )
    ]
    meetings.sort(
        key=lambda obj: (
            _meta(obj).get(KEY_MEETING_DATE) or "",
            _meta(obj).get(KEY_MEETING_NUMBER) or "",
            str(obj.id),
        ),
        reverse=True,
    )
    return meetings


def actions_of_meeting(
    repository: ObjectRepository, meeting_id: str
) -> list[UniversalObject]:
    """Every action item (task) BELONGS_TO this meeting (title-ordered)."""
    actions = [
        obj
        for obj in repository.find_by_type(ObjectType.TASK)
        if any(
            rel.kind is RelationshipKind.BELONGS_TO and str(rel.target) == meeting_id
            for rel in obj.relationships
        )
    ]
    actions.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return actions


# ---------------------------------------------------------------------------
# Output shapers
# ---------------------------------------------------------------------------
def meeting_summary_output(obj: UniversalObject) -> MeetingSummaryOutput:
    meta = _meta(obj)
    return MeetingSummaryOutput(
        id=str(obj.id),
        title=obj.title,
        meeting_number=meta.get(KEY_MEETING_NUMBER),
        meeting_date=meta.get(KEY_MEETING_DATE),
        venue=meta.get(KEY_VENUE),
        mode=meta.get(KEY_MODE),
        status=obj.status.value,
    )


def action_item_output(
    obj: UniversalObject,
    *,
    meeting: UniversalObject | None = None,
    committee: UniversalObject | None = None,
) -> ActionItemOutput:
    meta = _meta(obj)
    return ActionItemOutput(
        id=str(obj.id),
        title=obj.title,
        status=(meta.get(KEY_ACTION_STATUS) or "pending"),
        assigned_to=meta.get(KEY_ASSIGNED_TO) or None,
        assigned_name=meta.get(KEY_ASSIGNED_NAME) or None,
        due_date=meta.get(KEY_DUE_DATE),
        priority=meta.get(KEY_PRIORITY),
        progress=int(meta.get(KEY_PROGRESS) or 0),
        completion_date=meta.get(KEY_COMPLETION_DATE),
        remarks=meta.get(KEY_REMARKS),
        meeting=link_dict(meeting, RelationshipKind.BELONGS_TO) if meeting else None,
        committee=link_dict(committee, RelationshipKind.RELATED_TO) if committee else None,
    )


# ---------------------------------------------------------------------------
# Members (PART 2): resolve + leadership names for the filters
# ---------------------------------------------------------------------------
def member_rows(obj: UniversalObject) -> list[dict]:
    return parse_json_object_list(_meta(obj).get(KEY_MEMBERS))


def resolve_members(
    repository: ObjectRepository, obj: UniversalObject
) -> list[MemberView]:
    """Denormalise the committee's members against live person Objects."""
    rows = member_rows(obj)
    ids = [str(row.get("faculty_id") or "").strip() for row in rows]
    by_id = {str(found.id): found for found in repository.find_by_ids(ids)}
    views: list[MemberView] = []
    for row in rows:
        person = by_id.get(str(row.get("faculty_id") or "").strip())
        if person is None:
            continue  # deleted people records are skipped (frozen tolerance)
        views.append(
            MemberView(
                id=str(person.id),
                name=person.title,
                object_type=person.object_type.value,
                role=str(row.get("role") or "member"),
                start_date=row.get("start_date") or None,
                end_date=row.get("end_date") or None,
                remarks=row.get("remarks") or None,
            )
        )
    # Chairperson / convener / coordinator first, then the rest by name.
    rank = {"chairperson": 0, "convener": 1, "coordinator": 2}
    views.sort(
        key=lambda view: (
            rank.get(view.role, 9),
            view.name.casefold(),
            view.id,
        )
    )
    return views


def member_names_of_committee(
    repository: ObjectRepository, obj: UniversalObject
) -> str:
    """All member names joined — the chairperson/people-search haystack."""
    return " ".join(view.name for view in resolve_members(repository, obj))


def leadership_names_of_committee(
    repository: ObjectRepository, obj: UniversalObject, leadership_roles: tuple[str, ...]
) -> str:
    names = [
        view.name
        for view in resolve_members(repository, obj)
        if view.role in leadership_roles
    ]
    return " ".join(names)


# ---------------------------------------------------------------------------
# Committee → meetings/action counters (workspace stats + dashboard)
# ---------------------------------------------------------------------------
def committee_action_counts(
    repository: ObjectRepository, committee_id: str
) -> dict[str, int]:
    pending = completed = 0
    for meeting in meetings_of_committee(repository, committee_id):
        for action in actions_of_meeting(repository, str(meeting.id)):
            status = _meta(action).get(KEY_ACTION_STATUS) or "pending"
            if status == "done":
                completed += 1
            else:
                pending += 1
    return {"pending": pending, "completed": completed}


def enrich_committee_output(
    repository: ObjectRepository, obj: UniversalObject, output
) -> None:
    """Fill the workspace sections of a CommitteeOutput in place (members,
    meetings list, stats) — the single enrichment used by create/get/update."""
    output.members = resolve_members(repository, obj)
    meetings = meetings_of_committee(repository, str(obj.id))
    output.meetings = [meeting_summary_output(meeting) for meeting in meetings]
    counts = committee_action_counts(repository, str(obj.id))
    output.stats = {
        "meetings": len(meetings),
        "pending_actions": counts["pending"],
        "completed_actions": counts["completed"],
    }
