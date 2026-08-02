"""Data Transfer Objects for the Committees & Meetings use cases.

Mirrors ``dtos/research.py`` / ``dtos/faculty.py`` one-to-one: plain
framework-free dataclasses. Both a Committee and a Meeting are Universal
Objects — ``object_type = committee`` / ``object_type = meeting`` have existed
in the frozen catalogue since module 1, and action items ride on the equally
frozen ``task`` type. **No enum appends and no new DB model are needed by
this module.**

Graph doctrine (same as every module before):

  committee        committee Universal Object; directory fields are L6
                   human-asserted metadata (code/type/department/dates/…)
  members          ``members`` JSON list-of-dicts on the committee
                   [{faculty_id, role, start, end, remarks}] — the
                   publications ``authors`` precedent — PLUS a graph backlink
                   ``faculty MEMBER_OF → committee`` written on the member's
                   aggregate (the research-team multi-aggregate write
                   precedent) so the frozen faculty workspace keeps resolving
                   committee memberships live
  links (PART 7)   committee RELATED_TO → project / grant / student /
                   publication (the project-committees edge precedent)
  meetings         ``meeting`` children, meeting BELONGS_TO → committee
                   (the milestone doctrine: fields in metadata, embedded in
                   the parent's enriched GET, cascaded on delete)
  action items     ``task`` children, task BELONGS_TO → meeting — first-class
                   Objects so the dashboard's pending/completed counters and
                   any assignee lens come free
  documents        NOT duplicated: the frontend composes the existing
                   ``GET /documents?object_id=…`` lens on both the committee
                   (office orders, letters, reports) and the meeting
                   (agenda, minutes, attendance sheets) pages

Identity / de-duplication (registry doctrine, like project codes / employee
ids): ``committee_code`` is unique when provided (409), and the
(name, committee_type, department) triple is unique (409) so the same
committee name can still be registered for different departments/types.
``meeting_number`` is unique per committee (409).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list  # noqa: F401  (re-export)
from app.application.dtos.research import (
    link_dict,
    linked_target_ids,
    parse_json_object_list,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind

# ---------------------------------------------------------------------------
# Metadata keys — Committee directory (frozen convention; all L6 asserted)
# ---------------------------------------------------------------------------
KEY_COMMITTEE_CODE = "committee_code"  # unique when provided (409 on duplicate)
KEY_COMMITTEE_TYPE = "committee_type"
KEY_DEPARTMENT = "department"
KEY_SCHOOL = "school"
KEY_DESCRIPTION = "description"
KEY_CONSTITUTION_DATE = "constitution_date"
KEY_EXPIRY_DATE = "expiry_date"
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]

# Members (PART 2) — JSON list-of-dicts, {faculty_id, role, start, end, remarks}.
KEY_MEMBERS = "members"

# Meeting registry (PART 3) — metadata on the meeting child Object.
KEY_MEETING_NUMBER = "meeting_number"  # unique per committee (409 on duplicate)
KEY_MEETING_DATE = "meeting_date"
KEY_VENUE = "venue"
KEY_MODE = "mode"  # offline | online | hybrid
KEY_AGENDA_ITEMS = "agenda_items"  # JSON list-of-dicts (PART 4)
KEY_MINUTES = "minutes"
KEY_ATTENDANCE = "attendance"  # JSON list-of-dicts {object_id, name, status}
KEY_DECISIONS = "decisions"  # JSON list[str]
KEY_REMARKS = "remarks"

# Action items (PART 5) — metadata on the task child Object.
KEY_ASSIGNED_TO = "assigned_to"  # faculty ObjectId (optional)
KEY_ASSIGNED_NAME = "assigned_name"  # denormalised display name (externals allowed)
KEY_DUE_DATE = "due_date"
KEY_PRIORITY = "priority"  # high | medium | low
KEY_ACTION_STATUS = "action_status"  # pending | in_progress | done
KEY_PROGRESS = "progress"  # "0".."100"
KEY_COMPLETION_DATE = "completion_date"

# Committee type vocabulary (PART 1) — guidance, not a closed enum; custom
# committee types are allowed as free text.
COMMITTEE_TYPES = (
    "Purchase Committee",
    "Research Committee",
    "Department Research Committee (DRC)",
    "Board of Studies (BoS)",
    "Academic Council",
    "Finance Committee",
    "Examination Committee",
    "Selection Committee",
    "Internal Quality Assurance Cell (IQAC)",
)

# Member roles (PART 2) — the closed vocabulary from the spec.
MEMBER_ROLES = (
    "chairperson",
    "convener",
    "coordinator",
    "member",
    "external_expert",
    "student_member",
    "observer",
    "nominee",
)
LEADERSHIP_ROLES = ("chairperson", "convener", "coordinator")

# Meeting vocabulary.
MEETING_MODES = ("offline", "online", "hybrid")
# Agenda item fields (PART 4): {title, priority, presenter, discussion,
# decision, status, document_ids[]}.
AGENDA_PRIORITIES = ("high", "medium", "low")
AGENDA_ITEM_STATUSES = ("pending", "discussed", "decided", "deferred")
# Attendance entry: {object_id | name, status}.
ATTENDANCE_STATUSES = ("present", "absent", "leave")
# Action tracker vocabulary (PART 5).
ACTION_PRIORITIES = ("high", "medium", "low")
ACTION_STATUSES = ("pending", "in_progress", "done")

# ---------------------------------------------------------------------------
# Link groups — committee ↔ research/scholarly graph (PART 7)
# ---------------------------------------------------------------------------
COMMITTEE_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "projects": RelationshipKind.RELATED_TO,
    "grants": RelationshipKind.RELATED_TO,
    "students": RelationshipKind.RELATED_TO,
    "publications": RelationshipKind.RELATED_TO,
}
COMMITTEE_LINK_GROUPS = tuple(COMMITTEE_GROUP_TO_KIND.keys())

# The accepted target type per link group (422 on a mismatch — the faculty
# "committees expects committee targets" precedent).
COMMITTEE_GROUP_TARGET_TYPE: dict[str, ObjectType] = {
    "projects": ObjectType.RESEARCH_PROJECT,
    "grants": ObjectType.GRANT,
    "students": ObjectType.STUDENT,
    "publications": ObjectType.PUBLICATION,
}

_GROUP_TARGET_TO_GROUP: dict[ObjectType, str] = {
    ObjectType.RESEARCH_PROJECT: "projects",
    ObjectType.GRANT: "grants",
    ObjectType.STUDENT: "students",
    ObjectType.PUBLICATION: "publications",
}


def committee_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The committee link group an outgoing committee edge belongs to."""
    if kind is RelationshipKind.RELATED_TO:
        return _GROUP_TARGET_TO_GROUP.get(target_type)
    return None


def grouped_committee_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in COMMITTEE_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = committee_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def dumps_items(items: list) -> str:
    """Canonical storage string for a list section (JSON ensure-ascii off)."""
    return json.dumps(items, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Boundary DTOs — committee inputs
# ---------------------------------------------------------------------------
@dataclass
class CreateCommitteeInput:
    name: str  # -> Object title
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    committee_code: str | None = None
    committee_type: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    constitution_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    # PART 2 members — [{faculty_id, role, start_date, end_date, remarks}].
    members: list[dict] = field(default_factory=list)
    # PART 7 links — RELATE_TO edges written on the committee aggregate.
    projects: list[str] = field(default_factory=list)
    grants: list[str] = field(default_factory=list)
    students: list[str] = field(default_factory=list)
    publications: list[str] = field(default_factory=list)


@dataclass
class UpdateCommitteeInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    name: str | None = None
    status: ObjectStatus | None = None
    committee_code: str | None = None
    committee_type: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    constitution_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    members: list[dict] | None = None
    projects: list[str] | None = None
    grants: list[str] | None = None
    students: list[str] | None = None
    publications: list[str] | None = None


# ---------------------------------------------------------------------------
# Boundary DTOs — meeting + action item inputs
# ---------------------------------------------------------------------------
@dataclass
class CreateMeetingInput:
    title: str  # -> Object title ("6th BoS Meeting" etc.)
    committee_id: str
    created_by: str
    meeting_number: str | None = None  # unique per committee (409)
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    agenda_items: list[dict] = field(default_factory=list)  # PART 4
    minutes: str | None = None
    attendance: list[dict] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    remarks: str | None = None


@dataclass
class UpdateMeetingInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    title: str | None = None
    meeting_number: str | None = None
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    agenda_items: list[dict] | None = None
    minutes: str | None = None
    attendance: list[dict] | None = None
    decisions: list[str] | None = None
    remarks: str | None = None


@dataclass
class CreateActionItemInput:
    title: str  # the action to track -> Object title
    meeting_id: str
    created_by: str
    assigned_to: str | None = None  # faculty ObjectId
    due_date: str | None = None
    priority: str | None = None  # high | medium | low
    status: str = "pending"
    progress: int = 0
    completion_date: str | None = None
    remarks: str | None = None


@dataclass
class UpdateActionItemInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    title: str | None = None
    assigned_to: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str | None = None
    progress: int | None = None
    completion_date: str | None = None
    remarks: str | None = None


# ---------------------------------------------------------------------------
# Enriched read models
# ---------------------------------------------------------------------------
@dataclass
class MemberView:
    """One resolved committee member (metadata row + denormalised person)."""

    id: str  # the faculty/student ObjectId
    name: str
    object_type: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    remarks: str | None = None


@dataclass
class MeetingSummaryOutput:
    """A meeting row embedded in the committee workspace payload."""

    id: str
    title: str
    meeting_number: str | None
    meeting_date: str | None
    venue: str | None
    mode: str | None
    status: str


@dataclass
class ActionItemOutput:
    id: str
    title: str
    status: str
    assigned_to: str | None = None
    assigned_name: str | None = None
    due_date: str | None = None
    priority: str | None = None
    progress: int = 0
    completion_date: str | None = None
    remarks: str | None = None
    meeting: dict | None = None  # link_dict of the parent meeting
    committee: dict | None = None  # link_dict of the grandparent committee


@dataclass
class CommitteeOutput:
    """Read-side projection of a Committee Object (enriched workspace payload)."""

    id: str
    name: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    committee_code: str | None = None
    committee_type: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    constitution_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    members: list[MemberView] = field(default_factory=list)
    meetings: list[MeetingSummaryOutput] = field(default_factory=list)
    links: dict[str, list[dict]] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> CommitteeOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return CommitteeOutput(
            id=str(obj.id),
            name=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            committee_code=meta.get(KEY_COMMITTEE_CODE),
            committee_type=meta.get(KEY_COMMITTEE_TYPE),
            department=meta.get(KEY_DEPARTMENT),
            school=meta.get(KEY_SCHOOL),
            description=meta.get(KEY_DESCRIPTION),
            constitution_date=meta.get(KEY_CONSTITUTION_DATE),
            expiry_date=meta.get(KEY_EXPIRY_DATE),
            notes=meta.get(KEY_NOTES),
            tags=parse_json_list(meta.get(KEY_TAGS)),
            links=grouped_committee_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


@dataclass
class MeetingOutput:
    """Read-side projection of a Meeting Object (the meeting workspace)."""

    id: str
    title: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    meeting_number: str | None = None
    meeting_date: str | None = None
    venue: str | None = None
    mode: str | None = None
    agenda_items: list[dict] = field(default_factory=list)
    minutes: str | None = None
    attendance: list[dict] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    remarks: str | None = None
    committee: dict | None = None
    action_items: list[ActionItemOutput] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> MeetingOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        committee = None
        for rel in obj.relationships:
            if rel.kind is RelationshipKind.BELONGS_TO:
                target = (linked_by_id or {}).get(str(rel.target))
                if target is not None and target.object_type is ObjectType.COMMITTEE:
                    committee = link_dict(target, rel.kind)
        return MeetingOutput(
            id=str(obj.id),
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            meeting_number=meta.get(KEY_MEETING_NUMBER),
            meeting_date=meta.get(KEY_MEETING_DATE),
            venue=meta.get(KEY_VENUE),
            mode=meta.get(KEY_MODE),
            agenda_items=parse_json_object_list(meta.get(KEY_AGENDA_ITEMS)),
            minutes=meta.get(KEY_MINUTES),
            attendance=parse_json_object_list(meta.get(KEY_ATTENDANCE)),
            decisions=parse_json_list(meta.get(KEY_DECISIONS)),
            remarks=meta.get(KEY_REMARKS),
            committee=committee,
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


@dataclass
class ListCommitteesResult:
    items: list[CommitteeOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class CommitteesDashboard:
    """PART 8 dashboard cards (computed read — no stored counters)."""

    total_committees: int
    active_committees: int
    meetings_this_month: int
    pending_actions: int
    completed_actions: int
    upcoming_meetings: list[dict]  # [{meeting_id, committee_id, committee_title, title, date, venue, mode}]


# Re-exports used by the use cases (single-import convenience mirrors).
__all__ = [
    "link_dict",
    "linked_target_ids",
    "parse_json_object_list",
]
