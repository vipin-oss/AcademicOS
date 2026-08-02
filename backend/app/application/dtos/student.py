"""Data Transfer Objects for the Student use cases (Teaching & Students).

Mirrors ``dtos/publication.py``: plain framework-free dataclasses. A Student
is a Universal Object with ``object_type = student`` (Blueprint §2); every
registry field (roll no, programme, …) rides in the seven-layer metadata
record as L6 human-asserted, and every "Student ↔ X" edge is an asserted
relationship on the frozen domain model.

Identity / de-duplication: ``roll_number`` (primary, case-insensitive) and
``university_enrollment`` are unique per institution — creating a student
whose roll number or enrollment already exists is a 409, never a silent
variant.

Link groups: unlike Publications (grouped by target type alone), the two
supervision groups share the Faculty target type, so groups are derived from
(relationship kind, target type):

  supervisors      SUPERVISED_BY → faculty    (primary supervisor first)
  co_supervisors   ADVISED_BY    → faculty
  projects         WORKS_IN      → research_project
  grants           FUNDED_BY     → grant
  committees       MEMBER_OF     → committee
  events           PRESENTED_AT  → event

Publications and documents of a student are NOT duplicated here — the
frontend composes them through the existing object lenses
(``GET /publications?object_id=…`` / ``GET /documents?object_id=…``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# ---------------------------------------------------------------------------
# Metadata keys (frozen convention; all L6 / human-asserted)
# ---------------------------------------------------------------------------
KEY_STUDENT_TYPE = "student_type"  # ug | pg | phd | alumni
KEY_ROLL_NUMBER = "roll_number"
KEY_REGISTRATION_NUMBER = "registration_number"
KEY_UNIVERSITY_ENROLLMENT = "university_enrollment"
KEY_EMAIL = "email"
KEY_PHONE = "phone"
KEY_PROGRAMME = "programme"  # e.g. "BSc Mathematics with Data Science"
KEY_DEPARTMENT = "department"
KEY_SEMESTER = "semester"  # current semester, 1..12
KEY_SECTION = "section"
KEY_BATCH = "batch"  # admission year cohort, e.g. "2024-28"
KEY_ADMISSION_DATE = "admission_date"
KEY_EXPECTED_GRADUATION = "expected_graduation"
KEY_RESEARCH_AREA = "research_area"
KEY_ORCID = "orcid"
KEY_GOOGLE_SCHOLAR = "google_scholar"
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]

STUDENT_TYPES = ("ug", "pg", "phd", "alumni")

# ---------------------------------------------------------------------------
# Link groups -> relationship kind used when the edge is written.
# Group membership on read is derived from (kind, TARGET object_type).
# ---------------------------------------------------------------------------
GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "supervisors": RelationshipKind.SUPERVISED_BY,
    "co_supervisors": RelationshipKind.ADVISED_BY,
    "projects": RelationshipKind.WORKS_IN,
    "grants": RelationshipKind.FUNDED_BY,
    "committees": RelationshipKind.MEMBER_OF,
    "events": RelationshipKind.PRESENTED_AT,
}

LINK_GROUPS = tuple(GROUP_TO_KIND.keys())


def edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The link group an edge belongs to, or ``None`` if not student-facing."""
    if kind is RelationshipKind.SUPERVISED_BY and target_type is ObjectType.FACULTY:
        return "supervisors"
    if kind is RelationshipKind.ADVISED_BY and target_type is ObjectType.FACULTY:
        return "co_supervisors"
    if kind is RelationshipKind.WORKS_IN and target_type is ObjectType.RESEARCH_PROJECT:
        return "projects"
    if kind is RelationshipKind.FUNDED_BY and target_type is ObjectType.GRANT:
        return "grants"
    if kind is RelationshipKind.MEMBER_OF and target_type is ObjectType.COMMITTEE:
        return "committees"
    if kind is RelationshipKind.PRESENTED_AT and target_type is ObjectType.EVENT:
        return "events"
    return None


def linked_target_ids(obj: UniversalObject, kind: RelationshipKind | None = None) -> list[ObjectId]:
    """Ids of Objects this student links out to (optionally by kind)."""
    return [r.target for r in obj.relationships if kind is None or r.kind is kind]


def grouped_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    """Denormalised relationship edges grouped for the response payload."""
    links: dict[str, list[dict]] = {group: [] for group in LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = edge_group(rel.kind, target.object_type)
        if group is None:
            continue
        links[group].append(
            {
                "id": str(target.id),
                "title": target.title,
                "object_type": target.object_type.value,
                "kind": rel.kind.value,
            }
        )
    return links


# ---------------------------------------------------------------------------
# Boundary DTOs
# ---------------------------------------------------------------------------
@dataclass
class CreateStudentInput:
    """Boundary input for admitting a Student (manual entry / CSV import)."""

    name: str  # -> Object title
    created_by: str
    student_type: str
    status: ObjectStatus = ObjectStatus.DRAFT
    roll_number: str | None = None
    registration_number: str | None = None
    university_enrollment: str | None = None
    email: str | None = None
    phone: str | None = None
    programme: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    batch: str | None = None
    admission_date: str | None = None
    expected_graduation: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    google_scholar: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class UpdateStudentInput:
    """Partial update — the frozen publication-slice update contract:

    ``None`` = untouched; a provided value replaces. Link groups keep the
    proven merge semantics: a group present in ``links`` replaces exactly
    that group; absent groups are untouched.
    """

    actor: str
    name: str | None = None
    status: ObjectStatus | None = None
    student_type: str | None = None
    roll_number: str | None = None
    registration_number: str | None = None
    university_enrollment: str | None = None
    email: str | None = None
    phone: str | None = None
    programme: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    batch: str | None = None
    admission_date: str | None = None
    expected_graduation: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    google_scholar: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class StudentOutput:
    """Read-side projection of a Student Object."""

    id: str
    name: str
    student_type: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    roll_number: str | None = None
    registration_number: str | None = None
    university_enrollment: str | None = None
    email: str | None = None
    phone: str | None = None
    programme: str | None = None
    department: str | None = None
    semester: int | None = None
    section: str | None = None
    batch: str | None = None
    admission_date: str | None = None
    expected_graduation: str | None = None
    research_area: str | None = None
    orcid: str | None = None
    google_scholar: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    links: dict[str, list[dict]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ projection
    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> StudentOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        def as_int(key: str) -> int | None:
            raw = meta.get(key)
            if raw is None or raw == "":
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        return StudentOutput(
            id=str(obj.id),
            name=obj.title,
            student_type=meta.get(KEY_STUDENT_TYPE) or "ug",
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None,
            roll_number=meta.get(KEY_ROLL_NUMBER),
            registration_number=meta.get(KEY_REGISTRATION_NUMBER),
            university_enrollment=meta.get(KEY_UNIVERSITY_ENROLLMENT),
            email=meta.get(KEY_EMAIL),
            phone=meta.get(KEY_PHONE),
            programme=meta.get(KEY_PROGRAMME),
            department=meta.get(KEY_DEPARTMENT),
            semester=as_int(KEY_SEMESTER),
            section=meta.get(KEY_SECTION),
            batch=meta.get(KEY_BATCH),
            admission_date=meta.get(KEY_ADMISSION_DATE),
            expected_graduation=meta.get(KEY_EXPECTED_GRADUATION),
            research_area=meta.get(KEY_RESEARCH_AREA),
            orcid=meta.get(KEY_ORCID),
            google_scholar=meta.get(KEY_GOOGLE_SCHOLAR),
            notes=meta.get(KEY_NOTES),
            tags=list(parse_json_list(meta.get(KEY_TAGS))),
            links=grouped_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )

    def to_record(self) -> dict:
        """Flat record for CSV export / import-friendly serialization."""
        return {
            "name": self.name,
            "roll_number": self.roll_number,
            "registration_number": self.registration_number,
            "university_enrollment": self.university_enrollment,
            "email": self.email,
            "phone": self.phone,
            "student_type": self.student_type,
            "programme": self.programme,
            "department": self.department,
            "semester": self.semester,
            "section": self.section,
            "batch": self.batch,
            "admission_date": self.admission_date,
            "expected_graduation": self.expected_graduation,
            "research_area": self.research_area,
            "orcid": self.orcid,
            "google_scholar": self.google_scholar,
            "notes": self.notes,
            "tags": "; ".join(self.tags),
        }


@dataclass
class ListStudentsResult:
    items: list[StudentOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class ImportStudentsResult:
    """Outcome of a CSV roster import (FR: first-class CSV import)."""

    created: list[str] = field(default_factory=list)
    skipped_duplicates: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
