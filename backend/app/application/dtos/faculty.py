"""Data Transfer Objects for the Faculty Management use cases.

Mirrors ``dtos/research.py`` / ``dtos/student.py`` one-to-one: plain
framework-free dataclasses. A Faculty member is a Universal Object with
``object_type = faculty`` (Blueprint §2 — the type has existed in the frozen
catalogue since module 1); every directory field rides in the seven-layer
metadata record as L6 human-asserted, and every "Faculty ↔ X" edge is an
asserted relationship on the frozen domain model. **No enum appends and no
new DB model are needed by this module.**

Directory doctrine (PART 1): identity fields (employee id, faculty code,
designation, department, …), contact fields, scholar identifiers (ORCID,
Scopus, Google Scholar, ResearchGate, website) and free-text registry notes
are all flat metadata keys (publications/students convention). Academic
profile sections (PART 2: degrees, experience, awards, memberships,
certifications, administrative positions) are JSON list-of-dicts keys — the
publications ``authors`` / research ``progress_updates`` precedent.

Research integration (PART 3) and supervision (PART 4) are **derived
lenses**, never duplicated state:

  research      faculty LEADS/CO_LEADS/WORKS_IN → project (research module
                wrote these edges on the faculty aggregate); grants FUNDS →
                those projects (reverse scan over grants)
  supervision   student SUPERVISED_BY/ADVISED_BY → faculty (students module)
                — current (ug/pg/phd) vs completed (alumni)
  teaching      class TAUGHT_BY → faculty (teaching module) — weekly hours
                derived from the class's weekly schedule slots
  publications  publication AUTHORED_BY → faculty (publications module)
  committees    faculty MEMBER_OF → committee (written by THIS module — the
                only new edge the faculty module owns)
  documents     existing ``GET /documents?object_id=…`` lens

Profile photo (PART 1): the blob goes through the ``FileStorage`` port and
file facts ride as L2 system metadata (the attach_publication_pdf
precedent) — never in the relational row.

Identity / de-duplication (registry doctrine, like roll numbers / agency
names): ``employee_id`` is unique per institution (409 on duplicate) and
``faculty_code`` is unique when provided.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list
from app.application.dtos.research import (
    KEY_LIFECYCLE_STATUS,
    PROJECT_IN_FLIGHT_STATUSES,
    link_dict,
    linked_target_ids,
    parse_json_object_list,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# Re-exported so the use cases read one module only (no duplicate impl).
__all__: list[str] = []

# ---------------------------------------------------------------------------
# Metadata keys — Faculty directory (frozen convention; all L6 asserted)
# ---------------------------------------------------------------------------
KEY_EMPLOYEE_ID = "employee_id"  # unique per institution (409 on duplicate)
KEY_FACULTY_CODE = "faculty_code"  # unique when provided (409 on duplicate)
KEY_DESIGNATION = "designation"  # Professor, Associate Professor, …
KEY_DEPARTMENT = "department"
KEY_SCHOOL = "school"
KEY_JOINING_DATE = "joining_date"
KEY_EMPLOYMENT_TYPE = "employment_type"  # regular | contract | visiting | adjunct
KEY_EMAIL = "email"
KEY_MOBILE = "mobile"
KEY_OFFICE = "office"
KEY_QUALIFICATION = "qualification"  # e.g. "Ph.D. (IIT Delhi)"
KEY_SPECIALIZATION = "specialization"
KEY_RESEARCH_INTERESTS = "research_interests"  # JSON list[str]
KEY_BIOGRAPHY = "biography"
KEY_ORCID = "orcid"
KEY_SCOPUS_ID = "scopus_id"
KEY_GOOGLE_SCHOLAR = "google_scholar"
KEY_RESEARCHGATE = "researchgate"
KEY_WEBSITE = "website"
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]

# Academic profile sections (PART 2) — JSON list-of-dicts keys.
KEY_DEGREES = "degrees"  # [{degree, institution, year}]
KEY_EXPERIENCE = "experience"  # [{role, organization, from, to, note}]
KEY_AWARDS = "awards"  # [{title, year, by}]
KEY_MEMBERSHIPS = "memberships"  # [{body, year, note}]
KEY_CERTIFICATIONS = "certifications"  # [{title, issuer, year}]
KEY_ADMIN_POSITIONS = "admin_positions"  # [{position, unit, from, to}]

PROFILE_SECTION_KEYS: dict[str, tuple[str, ...]] = {
    KEY_DEGREES: ("degree", "institution", "year"),
    KEY_EXPERIENCE: ("role", "organization", "from", "to", "note"),
    KEY_AWARDS: ("title", "year", "by"),
    KEY_MEMBERSHIPS: ("body", "year", "note"),
    KEY_CERTIFICATIONS: ("title", "issuer", "year"),
    KEY_ADMIN_POSITIONS: ("position", "unit", "from", "to"),
}

# Profile photo — L2 filesystem facts (attach_publication_pdf precedent).
KEY_PHOTO_FILE_NAME = "photo_file_name"
KEY_PHOTO_FILE_PATH = "photo_file_path"
KEY_PHOTO_FILE_SIZE = "photo_file_size"
KEY_PHOTO_MIME_TYPE = "photo_mime_type"

# Registry vocabularies (guidance, not a closed enum — free text allowed).
DESIGNATIONS = (
    "Professor",
    "Associate Professor",
    "Assistant Professor",
    "Senior Lecturer",
    "Lecturer",
    "Professor of Practice",
    "Research Scientist",
    "Postdoctoral Fellow",
)
EMPLOYMENT_TYPES = ("regular", "contract", "visiting", "adjunct")

# The reverse-team edges the research module writes ON the faculty object.
RESEARCH_TEAM_KINDS = (
    RelationshipKind.LEADS,
    RelationshipKind.CO_LEADS,
    RelationshipKind.WORKS_IN,
)
SUPERVISION_KINDS = (RelationshipKind.SUPERVISED_BY, RelationshipKind.ADVISED_BY)

# ---------------------------------------------------------------------------
# Link groups — the ONLY edges the faculty module itself owns
# ---------------------------------------------------------------------------
FACULTY_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "committees": RelationshipKind.MEMBER_OF,
}
FACULTY_LINK_GROUPS = tuple(FACULTY_GROUP_TO_KIND.keys())


def faculty_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The faculty link group an outgoing faculty edge belongs to."""
    if kind is RelationshipKind.MEMBER_OF and target_type is ObjectType.COMMITTEE:
        return "committees"
    return None


def grouped_faculty_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in FACULTY_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = faculty_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def dumps_section(items: list[dict]) -> str:
    """Canonical storage string for a profile section (JSON list-of-dicts)."""
    return json.dumps(items, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Boundary DTOs — inputs
# ---------------------------------------------------------------------------
@dataclass
class CreateFacultyInput:
    name: str  # -> Object title
    employee_id: str  # registry identity — unique per institution (409)
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] = field(default_factory=list)
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    # Academic profile sections (PART 2) — each a list of plain dicts.
    degrees: list[dict] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    awards: list[dict] = field(default_factory=list)
    memberships: list[dict] = field(default_factory=list)
    certifications: list[dict] = field(default_factory=list)
    admin_positions: list[dict] = field(default_factory=list)
    # Committee memberships (MEMBER_OF edges on the faculty object).
    committees: list[str] = field(default_factory=list)


@dataclass
class UpdateFacultyInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    name: str | None = None
    employee_id: str | None = None
    status: ObjectStatus | None = None
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] | None = None
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    degrees: list[dict] | None = None
    experience: list[dict] | None = None
    awards: list[dict] | None = None
    memberships: list[dict] | None = None
    certifications: list[dict] | None = None
    admin_positions: list[dict] | None = None
    committees: list[str] | None = None


# ---------------------------------------------------------------------------
# Enriched read model — the faculty workspace payload
# ---------------------------------------------------------------------------
@dataclass
class FacultyOutput:
    """Read-side projection of a Faculty Object (enriched with derived lenses)."""

    id: str
    name: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    employee_id: str | None = None
    faculty_code: str | None = None
    designation: str | None = None
    department: str | None = None
    school: str | None = None
    joining_date: str | None = None
    employment_type: str | None = None
    email: str | None = None
    mobile: str | None = None
    office: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    research_interests: list[str] = field(default_factory=list)
    biography: str | None = None
    orcid: str | None = None
    scopus_id: str | None = None
    google_scholar: str | None = None
    researchgate: str | None = None
    website: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    # Academic profile sections
    degrees: list[dict] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    awards: list[dict] = field(default_factory=list)
    memberships: list[dict] = field(default_factory=list)
    certifications: list[dict] = field(default_factory=list)
    admin_positions: list[dict] = field(default_factory=list)
    # Profile photo facts (L2)
    photo_file_name: str | None = None
    photo_file_size: int = 0
    photo_mime_type: str | None = None
    photo_file_path: str | None = None
    # Edges the module owns
    links: dict[str, list[dict]] = field(default_factory=dict)
    # Derived lenses (PART 3/4/5) — filled by GetFacultyUseCase
    research: dict[str, list[dict]] = field(default_factory=dict)  # projects / grants
    supervision: dict[str, list[dict]] = field(default_factory=dict)  # current / completed
    teaching: dict[str, object] = field(default_factory=dict)  # classes / total_weekly_hours
    stats: dict[str, int] = field(default_factory=dict)  # PART 6 dashboard cards
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> FacultyOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return FacultyOutput(
            id=str(obj.id),
            name=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            employee_id=meta.get(KEY_EMPLOYEE_ID),
            faculty_code=meta.get(KEY_FACULTY_CODE),
            designation=meta.get(KEY_DESIGNATION),
            department=meta.get(KEY_DEPARTMENT),
            school=meta.get(KEY_SCHOOL),
            joining_date=meta.get(KEY_JOINING_DATE),
            employment_type=meta.get(KEY_EMPLOYMENT_TYPE),
            email=meta.get(KEY_EMAIL),
            mobile=meta.get(KEY_MOBILE),
            office=meta.get(KEY_OFFICE),
            qualification=meta.get(KEY_QUALIFICATION),
            specialization=meta.get(KEY_SPECIALIZATION),
            research_interests=parse_json_list(meta.get(KEY_RESEARCH_INTERESTS)),
            biography=meta.get(KEY_BIOGRAPHY),
            orcid=meta.get(KEY_ORCID),
            scopus_id=meta.get(KEY_SCOPUS_ID),
            google_scholar=meta.get(KEY_GOOGLE_SCHOLAR),
            researchgate=meta.get(KEY_RESEARCHGATE),
            website=meta.get(KEY_WEBSITE),
            notes=meta.get(KEY_NOTES),
            tags=parse_json_list(meta.get(KEY_TAGS)),
            degrees=parse_json_object_list(meta.get(KEY_DEGREES)),
            experience=parse_json_object_list(meta.get(KEY_EXPERIENCE)),
            awards=parse_json_object_list(meta.get(KEY_AWARDS)),
            memberships=parse_json_object_list(meta.get(KEY_MEMBERSHIPS)),
            certifications=parse_json_object_list(meta.get(KEY_CERTIFICATIONS)),
            admin_positions=parse_json_object_list(meta.get(KEY_ADMIN_POSITIONS)),
            photo_file_name=meta.get(KEY_PHOTO_FILE_NAME),
            photo_file_size=int(meta.get(KEY_PHOTO_FILE_SIZE) or 0),
            photo_mime_type=meta.get(KEY_PHOTO_MIME_TYPE),
            photo_file_path=meta.get(KEY_PHOTO_FILE_PATH),
            links=grouped_faculty_links(obj, linked_by_id or {}),
            research={"projects": [], "grants": []},
            supervision={"current": [], "completed": []},
            teaching={"classes": [], "total_weekly_hours": 0.0},
            stats={
                "publications": 0,
                "active_projects": 0,
                "grants": 0,
                "students_supervised": 0,
                "courses": 0,
                "committees": 0,
            },
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


@dataclass
class ListFacultyResult:
    items: list[FacultyOutput]
    total_count: int
    page: int
    page_size: int


# Re-exports used by the use cases (single-import convenience mirrors).
__all__ += [
    "KEY_LIFECYCLE_STATUS",
    "PROJECT_IN_FLIGHT_STATUSES",
    "link_dict",
    "linked_target_ids",
    "parse_json_object_list",
    "ObjectId",
]
