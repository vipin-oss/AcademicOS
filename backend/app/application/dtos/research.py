"""Data Transfer Objects for the Research Projects & Grants use cases.

Mirrors ``dtos/student.py`` / ``dtos/teaching.py`` one-to-one: plain
framework-free dataclasses. A Research Project is a Universal Object with
``object_type = research_project`` (Blueprint §2 — the type has existed since
module 1); every module field (code, lifecycle, budget, objectives, …) rides
in the seven-layer metadata record as L6 human-asserted, and every
"Project ↔ X" edge is an asserted relationship on the frozen domain model.

Lifecycle doctrine (frozen, enums.py §1.4): the 9-state research lifecycle
(draft → proposal_submitted → … → closed) is a *type-specific state* and is
therefore expressed as the ``lifecycle_status`` metadata key on top of the
universal draft/active/archived status — never as a separate model.

Edge ownership (mirrors the established module precedents):

  funding agency   project FUNDED_BY → funding_agency   (edge on the project)
  committees       project RELATED_TO → committee       (edge on the project)
  principal inv.   faculty LEADS → project              (edge on the faculty —
  co-investigators faculty CO_LEADS → project            the enroll_students
  team members     faculty/student WORKS_IN → project    multi-aggregate write)
  grant funding    grant FUNDED_BY → funding_agency      (edge on the grant)
  grant → projects grant FUNDS → research_project        (edge on the grant)
  children         milestone/installment/expenditure BELONGS_TO → parent

Publications and documents of a project are NOT duplicated here — the
frontend composes them through the existing object lenses
(``GET /publications?object_id=…`` / ``GET /documents?object_id=…``), and
team students also surface through ``GET /students?object_id=…``.

Identity / de-duplication (registry doctrine, like roll numbers): a Funding
Agency's *name* and a Grant's *grant_number* are unique per institution —
creating a duplicate is a 409, never a silent variant. A Project's
``project_code`` is unique when provided.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# ---------------------------------------------------------------------------
# Metadata keys — Funding Agency (frozen convention; all L6 / human-asserted)
# ---------------------------------------------------------------------------
KEY_AGENCY_WEBSITE = "agency_website"
KEY_AGENCY_SCHEME = "scheme"  # e.g. "Core Research Grant", "TARE"
KEY_AGENCY_CONTACT_PERSON = "contact_person"
KEY_AGENCY_EMAIL = "contact_email"
KEY_AGENCY_PHONE = "contact_phone"
KEY_AGENCY_ADDRESS = "address"

# ---------------------------------------------------------------------------
# Metadata keys — Research Project
# ---------------------------------------------------------------------------
KEY_PROJECT_CODE = "project_code"  # e.g. "DST-2024-0137" (unique when given)
KEY_LIFECYCLE_STATUS = "lifecycle_status"  # type-specific state, §1.4
KEY_DEPARTMENT = "department"
KEY_GRANT_NUMBER = "grant_number"  # sanction reference cited on the project
KEY_START_DATE = "start_date"
KEY_END_DATE = "end_date"
KEY_DURATION = "duration"  # free text, e.g. "36 months"
KEY_BUDGET_APPROVED = "budget_approved"  # decimal string, lakh/INR as entered
KEY_BUDGET_UTILIZED = "budget_utilized"  # decimal string
KEY_OBJECTIVES = "objectives"
KEY_KEYWORDS = "keywords"  # JSON list[str] (publications convention)
KEY_ABSTRACT = "abstract"
KEY_PRIORITY = "priority"  # high | medium | low
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]
KEY_PROGRESS_UPDATES = "progress_updates"  # JSON [{date, percent, remark}]

PROJECT_LIFECYCLE_STATUSES = (
    "draft",
    "proposal_submitted",
    "under_review",
    "approved",
    "funded",
    "active",
    "on_hold",
    "completed",
    "closed",
)
# Dashboard "Active Projects" card semantics: in-flight, non-terminal states.
PROJECT_IN_FLIGHT_STATUSES = ("approved", "funded", "active")
PROJECT_PRIORITIES = ("high", "medium", "low")

# ---------------------------------------------------------------------------
# Metadata keys — Grant / Installment / Expenditure / Milestone
# ---------------------------------------------------------------------------
KEY_AMOUNT = "amount"  # grant total / installment amount / expenditure amount
KEY_RELEASE_SCHEDULE = "release_schedule"  # e.g. "annual", "milestone-based"
KEY_INSTALLMENT_NO = "installment_no"  # 1-based int
KEY_INSTALLMENT_DATE = "installment_date"
KEY_INSTALLMENT_STATUS = "installment_status"  # scheduled | released
KEY_EXPENDITURE_DATE = "expenditure_date"
KEY_EXPENDITURE_HEAD = "expenditure_head"  # e.g. "Equipment", "Consumables"
KEY_EXPENDITURE_REFERENCE = "expenditure_reference"  # bill/PO/voucher ref
KEY_MILESTONE_DATE = "milestone_date"
KEY_MILESTONE_STATUS = "milestone_status"  # pending | in_progress | done

INSTALLMENT_STATUSES = ("scheduled", "released")
MILESTONE_STATUSES = ("pending", "in_progress", "done")

# ---------------------------------------------------------------------------
# Link groups (edges on the project / grant aggregate itself)
# ---------------------------------------------------------------------------
PROJECT_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "agencies": RelationshipKind.FUNDED_BY,
    "committees": RelationshipKind.RELATED_TO,
}
PROJECT_LINK_GROUPS = tuple(PROJECT_GROUP_TO_KIND.keys())

GRANT_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "projects": RelationshipKind.FUNDS,
    "funding_agencies": RelationshipKind.FUNDED_BY,
}
GRANT_LINK_GROUPS = tuple(GRANT_GROUP_TO_KIND.keys())

# Team groups: edges are written on the faculty/student aggregates (the
# multi-aggregate ``enroll_students`` precedent), never on the project.
TEAM_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "principal_investigators": RelationshipKind.LEADS,
    "co_investigators": RelationshipKind.CO_LEADS,
    "team_members": RelationshipKind.WORKS_IN,
}
TEAM_GROUPS = tuple(TEAM_GROUP_TO_KIND.keys())
TEAM_TARGET_TYPES = (ObjectType.FACULTY, ObjectType.STUDENT)


def project_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The project link group an outgoing project edge belongs to."""
    if kind is RelationshipKind.FUNDED_BY and target_type is ObjectType.FUNDING_AGENCY:
        return "agencies"
    if kind is RelationshipKind.RELATED_TO and target_type is ObjectType.COMMITTEE:
        return "committees"
    return None


def grant_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The grant link group an outgoing grant edge belongs to."""
    if kind is RelationshipKind.FUNDS and target_type is ObjectType.RESEARCH_PROJECT:
        return "projects"
    if kind is RelationshipKind.FUNDED_BY and target_type is ObjectType.FUNDING_AGENCY:
        return "funding_agencies"
    return None


def team_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The team group a *reverse* edge (person → project) belongs to."""
    if kind is RelationshipKind.LEADS and target_type is ObjectType.FACULTY:
        return "principal_investigators"
    if kind is RelationshipKind.CO_LEADS and target_type is ObjectType.FACULTY:
        return "co_investigators"
    if kind is RelationshipKind.WORKS_IN and target_type in TEAM_TARGET_TYPES:
        return "team_members"
    return None


def linked_target_ids(
    obj: UniversalObject, kind: RelationshipKind | None = None
) -> list[ObjectId]:
    """Ids of Objects this object links out to (optionally by kind)."""
    return [r.target for r in obj.relationships if kind is None or r.kind is kind]


def link_dict(target: UniversalObject, kind: RelationshipKind) -> dict:
    """Denormalised linked-Object payload (same shape as the students module)."""
    return {
        "id": str(target.id),
        "title": target.title,
        "object_type": target.object_type.value,
        "kind": kind.value,
    }


def grouped_project_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in PROJECT_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = project_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def grouped_grant_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in GRANT_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = grant_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def parse_json_object_list(raw: str | None) -> list[dict]:
    """JSON list-of-objects metadata (progress updates) — tolerant parse."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def parse_amount(raw: str | None) -> float | None:
    """Decimal metadata → float (None when absent/unparseable)."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return None


def format_amount(value: float | None) -> str | None:
    """Canonical storage string (plain decimal, no thousand separators)."""
    if value is None:
        return None
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


# ---------------------------------------------------------------------------
# Boundary DTOs — Funding Agency
# ---------------------------------------------------------------------------
@dataclass
class CreateAgencyInput:
    name: str  # -> Object title, unique per institution (409 on duplicate)
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    website: str | None = None
    scheme: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    notes: str | None = None


@dataclass
class UpdateAgencyInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    name: str | None = None
    status: ObjectStatus | None = None
    website: str | None = None
    scheme: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    notes: str | None = None


@dataclass
class AgencyOutput:
    id: str
    name: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    website: str | None = None
    scheme: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    notes: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(obj: UniversalObject, events: list) -> AgencyOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return AgencyOutput(
            id=str(obj.id),
            name=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            website=meta.get(KEY_AGENCY_WEBSITE),
            scheme=meta.get(KEY_AGENCY_SCHEME),
            contact_person=meta.get(KEY_AGENCY_CONTACT_PERSON),
            contact_email=meta.get(KEY_AGENCY_EMAIL),
            contact_phone=meta.get(KEY_AGENCY_PHONE),
            address=meta.get(KEY_AGENCY_ADDRESS),
            notes=meta.get(KEY_NOTES),
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class ListAgenciesResult:
    items: list[AgencyOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Boundary DTOs — Research Project
# ---------------------------------------------------------------------------
@dataclass
class MilestoneInput:
    title: str
    date: str  # YYYY-MM-DD
    status: str = "pending"
    notes: str | None = None


@dataclass
class UpdateMilestoneInput:
    """Partial milestone update (title/date/status/notes)."""

    actor: str
    title: str | None = None
    date: str | None = None
    status: str | None = None
    notes: str | None = None


@dataclass
class MilestoneOutput:
    id: str
    title: str
    date: str | None
    status: str
    notes: str | None = None


@dataclass
class ProgressUpdateInput:
    date: str  # YYYY-MM-DD
    percent: float  # 0..100
    remark: str


@dataclass
class ProjectBudget:
    """Simple MVP budget view (PART 7 — no accounting system)."""

    approved: float | None
    utilized: float | None
    remaining: float | None
    # Sum of released installments across the project's grant objects.
    grants_released: float | None


@dataclass
class CreateProjectInput:
    title: str  # -> Object title
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    lifecycle_status: str = "draft"
    project_code: str | None = None
    department: str | None = None
    grant_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    budget_approved: float | None = None
    budget_utilized: float | None = None
    objectives: str | None = None
    keywords: tuple[str, ...] = ()
    abstract: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    links: dict[str, tuple[ObjectId, ...]] | None = None  # agencies / committees
    team: dict[str, tuple[ObjectId, ...]] | None = None  # pi / co-pi / members


@dataclass
class UpdateProjectInput:
    """Partial update — frozen merge contract (None untouched; value replaces;

    a link/team group present replaces exactly that group, absent groups
    untouched).
    """

    actor: str
    title: str | None = None
    status: ObjectStatus | None = None
    lifecycle_status: str | None = None
    project_code: str | None = None
    department: str | None = None
    grant_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    budget_approved: float | None = None
    budget_utilized: float | None = None
    objectives: str | None = None
    keywords: tuple[str, ...] | None = None
    abstract: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None
    team: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class ProjectOutput:
    """Read-side projection of a Research Project Object."""

    id: str
    title: str
    status: str
    lifecycle_status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    project_code: str | None = None
    department: str | None = None
    grant_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    budget_approved: float | None = None
    budget_utilized: float | None = None
    objectives: str | None = None
    keywords: list[str] = field(default_factory=list)
    abstract: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    progress_updates: list[dict] = field(default_factory=list)
    links: dict[str, list[dict]] = field(default_factory=dict)
    team: dict[str, list[dict]] = field(default_factory=dict)
    milestones: list[MilestoneOutput] = field(default_factory=list)
    budget: dict | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> ProjectOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return ProjectOutput(
            id=str(obj.id),
            title=obj.title,
            status=obj.status.value,
            lifecycle_status=meta.get(KEY_LIFECYCLE_STATUS) or "draft",
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            project_code=meta.get(KEY_PROJECT_CODE),
            department=meta.get(KEY_DEPARTMENT),
            grant_number=meta.get(KEY_GRANT_NUMBER),
            start_date=meta.get(KEY_START_DATE),
            end_date=meta.get(KEY_END_DATE),
            duration=meta.get(KEY_DURATION),
            budget_approved=parse_amount(meta.get(KEY_BUDGET_APPROVED)),
            budget_utilized=parse_amount(meta.get(KEY_BUDGET_UTILIZED)),
            objectives=meta.get(KEY_OBJECTIVES),
            keywords=list(parse_json_list(meta.get(KEY_KEYWORDS))),
            abstract=meta.get(KEY_ABSTRACT),
            priority=meta.get(KEY_PRIORITY),
            notes=meta.get(KEY_NOTES),
            tags=list(parse_json_list(meta.get(KEY_TAGS))),
            progress_updates=parse_json_object_list(meta.get(KEY_PROGRESS_UPDATES)),
            links=grouped_project_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )

    def to_list_record(self) -> dict:
        """Compact dashboard/list row (mirrors StudentOutput.to_record)."""
        return {
            "title": self.title,
            "project_code": self.project_code,
            "lifecycle_status": self.lifecycle_status,
            "department": self.department,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "budget_approved": self.budget_approved,
            "budget_utilized": self.budget_utilized,
            "priority": self.priority,
        }


@dataclass
class ListProjectsResult:
    items: list[ProjectOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Boundary DTOs — Grant / Installment / Expenditure
# ---------------------------------------------------------------------------
@dataclass
class InstallmentInput:
    installment_no: int
    date: str  # YYYY-MM-DD
    amount: float
    status: str = "released"
    notes: str | None = None


@dataclass
class InstallmentOutput:
    id: str
    installment_no: int | None
    date: str | None
    amount: float | None
    status: str
    notes: str | None = None


@dataclass
class ExpenditureInput:
    date: str  # YYYY-MM-DD
    head: str  # budget head, e.g. "Equipment"
    amount: float
    reference: str | None = None
    notes: str | None = None


@dataclass
class ExpenditureOutput:
    id: str
    date: str | None
    head: str | None
    amount: float | None
    reference: str | None = None
    notes: str | None = None


@dataclass
class CreateGrantInput:
    title: str  # grant title -> Object title
    grant_number: str  # unique per institution (409 on duplicate)
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    amount: float | None = None
    release_schedule: str | None = None
    notes: str | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None  # projects / agencies


@dataclass
class UpdateGrantInput:
    """Partial update — frozen merge contract."""

    actor: str
    title: str | None = None
    grant_number: str | None = None
    status: ObjectStatus | None = None
    amount: float | None = None
    release_schedule: str | None = None
    notes: str | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class GrantOutput:
    """Read-side projection of a Grant Object (with computed budget)."""

    id: str
    title: str
    grant_number: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    amount: float | None = None
    release_schedule: str | None = None
    notes: str | None = None
    links: dict[str, list[dict]] = field(default_factory=dict)
    installments: list[InstallmentOutput] = field(default_factory=list)
    expenditures: list[ExpenditureOutput] = field(default_factory=list)
    budget: dict | None = None  # {approved, released, utilized, remaining}
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> GrantOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return GrantOutput(
            id=str(obj.id),
            title=obj.title,
            grant_number=meta.get(KEY_GRANT_NUMBER) or "",
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            amount=parse_amount(meta.get(KEY_AMOUNT)),
            release_schedule=meta.get(KEY_RELEASE_SCHEDULE),
            notes=meta.get(KEY_NOTES),
            links=grouped_grant_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class ListGrantsResult:
    items: list[GrantOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Boundary DTO — Research Dashboard (PART 10 cards + upcoming deadlines)
# ---------------------------------------------------------------------------
@dataclass
class UpcomingDeadline:
    milestone_id: str
    title: str
    date: str | None
    status: str
    project_id: str
    project_title: str


@dataclass
class ResearchDashboardOutput:
    total_projects: int
    active_projects: int
    completed_projects: int
    total_grants: int
    budget_approved: float
    budget_utilized: float
    upcoming_deadlines: list[UpcomingDeadline] = field(default_factory=list)
