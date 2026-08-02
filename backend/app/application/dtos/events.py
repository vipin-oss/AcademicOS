"""DTOs and metadata-key catalogue for the Events & Academic Activities slice.

Mirrors ``dtos/finance.py`` / ``dtos/committee.py`` one-to-one: every field
rides as L6 human-asserted metadata on Universal Objects; no new DB models,
no enum changes — ``ObjectType.EVENT`` has existed since the Domain
Foundation ("Operations & governance" catalogue).

One record kind:
  - Event -> ``ObjectType.EVENT`` with JSON list-of-dicts sections
    (participation / speakers / schedule / presentations), a JSON dict
    ``registration`` counter block, and plain scalar metadata for the PART 1
    record fields — the committee ``members`` / meeting ``agenda_items`` and
    proposal sections precedent.

Link groups to the people/research/governance graph ride as RELATED_TO
edges on the event aggregate (the finance PART 7 precedent); the
publications group is DERIVED from the ``presentations`` rows (PART 8) —
each row adds one RELATED_TO edge to its publication.

Dashboard cards (PART 9) are a computed read — no stored counters.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list  # noqa: F401  (re-export)
from app.application.dtos.research import (
    link_dict,  # noqa: F401  (re-export)
    linked_target_ids,  # noqa: F401  (re-export)
    parse_json_object_list,  # noqa: F401  (re-export)
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind

# ---------------------------------------------------------------------------
# Metadata keys — Event record (PART 1)
# ---------------------------------------------------------------------------
KEY_EVENT_CODE = "event_code"  # unique when provided (409 on duplicate)
KEY_EVENT_TYPE = "event_type"
KEY_ORGANIZER = "organizer"
KEY_CO_ORGANIZER = "co_organizer"
KEY_VENUE = "venue"
KEY_MODE = "mode"  # online | offline | hybrid
KEY_START_DATE = "start_date"
KEY_END_DATE = "end_date"
KEY_DEPARTMENT = "department"
KEY_SCHOOL = "school"
KEY_DESCRIPTION = "description"
KEY_OBJECTIVES = "objectives"
KEY_OUTCOME = "outcome"
KEY_EVENT_STATUS = "event_status"  # business lifecycle (metadata vocab)
KEY_PRIORITY = "priority"
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list of strings

# JSON sections (PARTS 2/3/4/5/8) — row shapes documented at the vocabularies
# below; extra keys are dropped by the normalisers.
KEY_PARTICIPATION = "participation"  # PART 2 "My Participation" rows
KEY_SPEAKERS = "speakers"  # PART 3 speaker directory rows
KEY_SCHEDULE = "schedule"  # PART 4 session rows
KEY_REGISTRATION = "registration"  # PART 5 counters {expected_participants, …}
KEY_PRESENTATIONS = "presentations"  # PART 8 publication links + relations

# ---------------------------------------------------------------------------
# Vocabularies (metadata-level — the universal ObjectStatus lifecycle stays
# draft/active/archived; these ride as human-asserted strings)
# ---------------------------------------------------------------------------
EVENT_TYPES = (
    "conference",
    "workshop",
    "seminar",
    "webinar",
    "fdp",
    "sttp",
    "expert_lecture",
    "guest_lecture",
    "invited_talk",
    "mathematics_day",
    "science_day",
    "orientation_programme",
    "training_programme",
    "industry_visit",
    "club_activity",
    "research_colloquium",
    "outreach_activity",
    "competition",
    "custom",
)
EVENT_STATUSES = ("planned", "ongoing", "postponed", "completed", "cancelled")
# Statuses that count as an "upcoming event" on the PART 9 dashboard
# (completed/cancelled are terminal).
UPCOMING_EVENT_STATUSES = ("planned", "ongoing", "postponed")
EVENT_MODES = ("online", "offline", "hybrid")
EVENT_PRIORITIES = ("high", "medium", "low")
PARTICIPATION_ROLES = (
    "organizer",
    "coordinator",
    "convener",
    "speaker",
    "session_chair",
    "participant",
    "volunteer",
    "resource_person",
    "chief_guest",
    "judge",
    "attendee",
)
PRESENTATION_RELATIONS = (
    "presented_paper",
    "published_proceedings",
    "best_paper_award",
    "poster_presentation",
)
# PART 9 card semantics (documented, deterministic — computed reads):
#   organized      -> my participation role is one of the organising chairs
#   attended       -> my participation role is one of the attendee chairs
#   presentations  -> publication links flagged as a live presentation
#   invited_talks  -> invited_talk events where I hold a speaking role
ORGANIZER_ROLES = ("organizer", "coordinator", "convener")
ATTENDEE_ROLES = ("participant", "attendee")
SPEAKING_ROLES = ("speaker", "resource_person")
PRESENTATION_COUNT_RELATIONS = ("presented_paper", "poster_presentation")

# Registration counter keys (PART 5) — all non-negative integers.
REGISTRATION_KEYS = (
    "expected_participants",
    "registered",
    "present",
    "certificates_issued",
)

# Section row whitelists (unknown keys dropped — the _normalise_member_rows
# precedent from the committees module). ``row_id`` on speakers is minted
# server-side when absent so schedule rows can reference a stable speaker;
# echoing it back on group-replace keeps the schedule link alive (the
# finance vendor_id precedent, inside one aggregate).
PARTICIPATION_ROW_KEYS = (
    "role",
    "contribution",
    "certificate_document_id",
    "remarks",
)
SPEAKER_ROW_KEYS = (
    "row_id",
    "name",
    "affiliation",
    "designation",
    "email",
    "phone",
    "biography",
    "photo_document_id",
    "document_ids",
)
SCHEDULE_ROW_KEYS = (
    "title",
    "session_date",
    "start_time",
    "end_time",
    "speaker_id",
    "venue",
    "chairperson",
    "remarks",
)
PRESENTATION_ROW_KEYS = (
    "publication_id",
    "relation",
    "remarks",
)

# ---------------------------------------------------------------------------
# Link groups — event ↔ people/research/governance graph (finance precedent)
# ---------------------------------------------------------------------------
EVENT_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "faculty": RelationshipKind.RELATED_TO,
    "students": RelationshipKind.RELATED_TO,
    "projects": RelationshipKind.RELATED_TO,
    "grants": RelationshipKind.RELATED_TO,
    "committees": RelationshipKind.RELATED_TO,
    "publications": RelationshipKind.RELATED_TO,
}
EVENT_LINK_GROUPS = tuple(EVENT_GROUP_TO_KIND.keys())
# Groups whose ids arrive on the wire (``presentations`` rows drive the
# ``publications`` edges instead of a plain id list — PART 8).
EVENT_INPUT_LINK_GROUPS = (
    "faculty",
    "students",
    "projects",
    "grants",
    "committees",
)

EVENT_GROUP_TARGET_TYPE: dict[str, ObjectType] = {
    "faculty": ObjectType.FACULTY,
    "students": ObjectType.STUDENT,
    "projects": ObjectType.RESEARCH_PROJECT,
    "grants": ObjectType.GRANT,
    "committees": ObjectType.COMMITTEE,
    "publications": ObjectType.PUBLICATION,
}

_GROUP_TARGET_TO_GROUP: dict[ObjectType, str] = {
    ObjectType.FACULTY: "faculty",
    ObjectType.STUDENT: "students",
    ObjectType.RESEARCH_PROJECT: "projects",
    ObjectType.GRANT: "grants",
    ObjectType.COMMITTEE: "committees",
    ObjectType.PUBLICATION: "publications",
}


def event_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The event link group an outgoing event edge belongs to."""
    if kind is RelationshipKind.RELATED_TO:
        return _GROUP_TARGET_TO_GROUP.get(target_type)
    return None


def grouped_event_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in EVENT_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = event_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def parse_json_object(raw: str | None) -> dict:
    """Parse a JSON object metadata value ({} when unset/invalid)."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Boundary inputs
# ---------------------------------------------------------------------------
@dataclass
class CreateEventInput:
    title: str  # -> Object title (Event Title)
    created_by: str
    status: ObjectStatus = ObjectStatus.ACTIVE
    event_code: str | None = None
    event_type: str = "custom"
    organizer: str | None = None
    co_organizer: str | None = None
    venue: str | None = None
    mode: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    objectives: str | None = None
    outcome: str | None = None
    event_status: str = "planned"
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    # PARTS 2-5 + 8 sections (list-of-dicts rows / registration dict).
    participation: list[dict] = field(default_factory=list)
    speakers: list[dict] = field(default_factory=list)
    schedule: list[dict] = field(default_factory=list)
    registration: dict = field(default_factory=dict)
    presentations: list[dict] = field(default_factory=list)
    # Link groups (RELATED_TO edges on the event aggregate).
    faculty: list[str] = field(default_factory=list)
    students: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    grants: list[str] = field(default_factory=list)
    committees: list[str] = field(default_factory=list)


@dataclass
class UpdateEventInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    title: str | None = None
    status: ObjectStatus | None = None
    event_code: str | None = None
    event_type: str | None = None
    organizer: str | None = None
    co_organizer: str | None = None
    venue: str | None = None
    mode: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    objectives: str | None = None
    outcome: str | None = None
    event_status: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    participation: list[dict] | None = None
    speakers: list[dict] | None = None
    schedule: list[dict] | None = None
    registration: dict | None = None
    presentations: list[dict] | None = None
    faculty: list[str] | None = None
    students: list[str] | None = None
    projects: list[str] | None = None
    grants: list[str] | None = None
    committees: list[str] | None = None


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass
class EventOutput:
    """Read-side projection of an Event Object (enriched workspace)."""

    id: str
    title: str
    status: str  # universal lifecycle
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    event_code: str | None = None
    event_type: str | None = None
    organizer: str | None = None
    co_organizer: str | None = None
    venue: str | None = None
    mode: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    department: str | None = None
    school: str | None = None
    description: str | None = None
    objectives: str | None = None
    outcome: str | None = None
    event_status: str = "planned"  # business lifecycle (metadata vocab)
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    participation: list[dict] = field(default_factory=list)
    speakers: list[dict] = field(default_factory=list)
    schedule: list[dict] = field(default_factory=list)
    registration: dict = field(default_factory=dict)
    presentations: list[dict] = field(default_factory=list)
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
    ) -> EventOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        registration = parse_json_object(meta.get(KEY_REGISTRATION))
        return EventOutput(
            id=str(obj.id),
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            event_code=meta.get(KEY_EVENT_CODE),
            event_type=meta.get(KEY_EVENT_TYPE),
            organizer=meta.get(KEY_ORGANIZER),
            co_organizer=meta.get(KEY_CO_ORGANIZER),
            venue=meta.get(KEY_VENUE),
            mode=meta.get(KEY_MODE),
            start_date=meta.get(KEY_START_DATE),
            end_date=meta.get(KEY_END_DATE),
            department=meta.get(KEY_DEPARTMENT),
            school=meta.get(KEY_SCHOOL),
            description=meta.get(KEY_DESCRIPTION),
            objectives=meta.get(KEY_OBJECTIVES),
            outcome=meta.get(KEY_OUTCOME),
            event_status=(meta.get(KEY_EVENT_STATUS) or "planned"),
            priority=meta.get(KEY_PRIORITY),
            notes=meta.get(KEY_NOTES),
            tags=parse_json_list(meta.get(KEY_TAGS)),
            participation=parse_json_object_list(meta.get(KEY_PARTICIPATION)),
            speakers=parse_json_object_list(meta.get(KEY_SPEAKERS)),
            schedule=parse_json_object_list(meta.get(KEY_SCHEDULE)),
            registration={
                key: int(registration.get(key) or 0) for key in REGISTRATION_KEYS
            },
            presentations=parse_json_object_list(meta.get(KEY_PRESENTATIONS)),
            links=grouped_event_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


# ---------------------------------------------------------------------------
# List/dashboard projections
# ---------------------------------------------------------------------------
@dataclass
class ListEventsResult:
    items: list[EventOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class EventsDashboard:
    """PART 9 dashboard cards (computed read — no stored counters)."""

    upcoming_events: int
    completed_events: int
    events_organized: int
    events_attended: int
    certificates: int
    presentations: int
    invited_talks: int


# Re-exports used by the use cases (single-import convenience mirrors).
__all__ = [
    "link_dict",
    "linked_target_ids",
    "parse_json_object_list",
]
