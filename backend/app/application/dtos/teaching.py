"""Data Transfer Objects for the Teaching use cases.

Mirrors ``dtos/publication.py`` / ``dtos/student.py``: plain framework-free
dataclasses over the frozen Universal Object model. Four object types work
together (Blueprint §2 catalogue, appended additively):

  Class              object_type = course    — a taught class / course offering
  Assignment         object_type = assignment — assessment belonging to a class
  Submission         object_type = submission — one per (assignment × student)
  AttendanceSession  object_type = attendance_session — one per (class × date)

Everything object-centric: fields ride the L6 metadata record (L2/SYSTEM for
file facts), membership/ownership is typed relationship edges, and every
aggregate view (submission grid, gradebook, class report, dashboard) is
COMPUTED from the same objects — no shadow tables, so future AI always reads
one source of truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# ---------------------------------------------------------------------------
# Metadata keys — Class
# ---------------------------------------------------------------------------
KEY_COURSE_CODE = "course_code"  # e.g. "CS-301"
KEY_PROGRAMME = "programme"  # owning programme, e.g. "BSc Mathematics w/ DS"
KEY_SEMESTER = "semester"  # 1..12
KEY_SECTION = "section"
KEY_SESSION = "session"  # academic session, e.g. "2026-27"
KEY_CREDITS = "credits"
KEY_WEEKLY_SCHEDULE = "weekly_schedule"  # JSON [{day, start, end}]
KEY_ROOM = "room"
KEY_CLASS_MODE = "class_mode"  # offline | online | blended
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list[str]

CLASS_MODES = ("offline", "online", "blended")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Class link groups: teachers TAUGHT_BY→faculty (reversed teaching edge is
# derived — the edge lives on the class, so the roster is one frozen call).
CLASS_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "teachers": RelationshipKind.TAUGHT_BY,
    "departments": RelationshipKind.BELONGS_TO,
}
CLASS_LINK_GROUPS = tuple(CLASS_GROUP_TO_KIND.keys())

# ---------------------------------------------------------------------------
# Metadata keys — Assignment
# ---------------------------------------------------------------------------
KEY_ASSIGNMENT_TYPE = "assignment_type"  # assignment|quiz|internal|mid|end
KEY_DESCRIPTION = "description"
KEY_INSTRUCTIONS = "instructions"
KEY_MAX_MARKS = "max_marks"
KEY_DEADLINE = "deadline"  # ISO date or datetime string
KEY_LATE_ALLOWED = "late_allowed"  # "true" | "false"
KEY_RUBRIC = "rubric"  # JSON [{criterion, marks}]
KEY_VISIBILITY = "visibility"  # visible | hidden
KEY_WEIGHTAGE = "weightage"  # % of the internal/external total
KEY_ATTACHMENT_NAME = "attachment_file_name"
KEY_ATTACHMENT_SIZE = "attachment_file_size"
KEY_ATTACHMENT_MIME = "attachment_mime_type"
KEY_ATTACHMENT_PATH = "attachment_file_path"

ASSIGNMENT_TYPES = (
    "assignment",
    "quiz",
    "internal_assessment",
    "mid_semester",
    "end_semester",
)
VISIBILITIES = ("visible", "hidden")

# Assessment "categories" used by the gradebook rollup (PART H):
# everything except end_semester counts as internal assessment by default.
INTERNAL_TYPES = ("assignment", "quiz", "internal_assessment", "mid_semester")

# ---------------------------------------------------------------------------
# Metadata keys — Submission (one per assignment × student)
# ---------------------------------------------------------------------------
KEY_SUBMITTED_AT = "submitted_at"  # ISO datetime (SYSTEM at upload)
KEY_IS_LATE = "is_late"  # "true" | "false" (computed at submit)
KEY_COMMENTS = "comments"  # student's note with the submission
KEY_MARKS = "marks"  # float, <= assignment max_marks
KEY_FACULTY_FEEDBACK = "faculty_feedback"
KEY_RUBRIC_SCORE = "rubric_score"  # JSON [{criterion, marks_awarded}]
KEY_GRADED_AT = "graded_at"
KEY_GRADED_BY = "graded_by"
KEY_FILE_NAME = "file_name"
KEY_FILE_SIZE = "file_size"
KEY_FILE_MIME = "file_mime_type"
KEY_FILE_PATH = "file_path"

# ---------------------------------------------------------------------------
# Metadata keys — AttendanceSession (PART I: architecture ready, CSV/manual)
# ---------------------------------------------------------------------------
KEY_SESSION_DATE = "session_date"  # the teaching day (YYYY-MM-DD)
KEY_ATTENDANCE_RECORDS = "attendance_records"  # JSON {student_id: state}

ATTENDANCE_STATES = ("present", "absent", "late", "medical_leave")

# Grade bands for the computed total (PART H): lower bound (inclusive) -> grade
GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (90.0, "A+"),
    (80.0, "A"),
    (70.0, "B+"),
    (60.0, "B"),
    (50.0, "C"),
    (40.0, "D"),
    (0.0, "F"),
)


def grade_for(total: float) -> str:
    """Letter grade for a 0–100 total (bounded by GRADE_BANDS)."""
    for lower, letter in GRADE_BANDS:
        if total >= lower:
            return letter
    return "F"


# ---------------------------------------------------------------------------
# JSON helpers built on the shared parser (numeric maps / lists of objects)
# ---------------------------------------------------------------------------
def encode_json(value) -> str:
    return json.dumps(value)


def parse_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_schedule(raw: str | None) -> list[dict]:
    """Weekly schedule rows: [{day, start, end}] — invalid rows dropped."""
    slots = []
    for entry in parse_json_list(raw):
        if isinstance(entry, dict) and entry.get("day") in WEEKDAYS:
            slots.append(
                {
                    "day": entry["day"],
                    "start": str(entry.get("start", "")),
                    "end": str(entry.get("end", "")),
                }
            )
    return slots


def parse_rubric(raw: str | None) -> list[dict]:
    """Rubric criteria: [{criterion, marks}] — invalid rows dropped."""
    criteria = []
    for entry in parse_json_list(raw):
        if isinstance(entry, dict) and entry.get("criterion"):
            try:
                marks = float(entry.get("marks", 0) or 0)
            except (ValueError, TypeError):
                marks = 0.0
            criteria.append({"criterion": str(entry["criterion"]), "marks": marks})
    return criteria


def parse_bool(raw: str | None, *, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Boundary DTOs — Class
# ---------------------------------------------------------------------------
@dataclass
class CreateClassInput:
    """Boundary input for creating a Class (course offering)."""

    title: str  # e.g. "Computer Fundamentals"
    created_by: str
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    session: str | None = None  # "2026-27"
    credits: float | None = None
    weekly_schedule: tuple[dict, ...] = ()
    room: str | None = None
    class_mode: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    status: ObjectStatus = ObjectStatus.DRAFT
    links: dict[str, tuple[ObjectId, ...]] | None = None  # teachers / departments
    students: tuple[ObjectId, ...] = ()  # initial enrollment (ENROLLED_IN)


@dataclass
class UpdateClassInput:
    """Partial class update: ``None`` = untouched; a provided value replaces
    (the frozen publication-slice update contract)."""

    actor: str
    title: str | None = None
    status: ObjectStatus | None = None
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    session: str | None = None
    credits: float | None = None
    weekly_schedule: tuple[dict, ...] | None = None
    room: str | None = None
    class_mode: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] | None = None
    links: dict[str, tuple[ObjectId, ...]] | None = None


@dataclass
class ClassOutput:
    """Read-side projection of a Class Object."""

    id: str
    title: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    course_code: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    session: str | None = None
    credits: float | None = None
    weekly_schedule: list[dict] = field(default_factory=list)
    room: str | None = None
    class_mode: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    student_count: int = 0  # enrollment size (convenience projection)
    links: dict[str, list[dict]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
        student_count: int = 0,
    ) -> ClassOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        def as_int(key: str) -> int | None:
            raw = meta.get(key)
            try:
                return int(raw) if raw not in (None, "") else None
            except ValueError:
                return None

        def as_float(key: str) -> float | None:
            raw = meta.get(key)
            try:
                return float(raw) if raw not in (None, "") else None
            except ValueError:
                return None

        links: dict[str, list[dict]] = {group: [] for group in CLASS_LINK_GROUPS}
        for rel in obj.relationships:
            target = (linked_by_id or {}).get(str(rel.target))
            if target is None:
                continue
            if rel.kind is RelationshipKind.TAUGHT_BY and target.object_type is ObjectType.FACULTY:
                links["teachers"].append(
                    {"id": str(target.id), "title": target.title,
                     "object_type": target.object_type.value, "kind": rel.kind.value}
                )
            elif rel.kind is RelationshipKind.BELONGS_TO:
                links["departments"].append(
                    {"id": str(target.id), "title": target.title,
                     "object_type": target.object_type.value, "kind": rel.kind.value}
                )

        return ClassOutput(
            id=str(obj.id),
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat()
                if obj.audit is not None and obj.audit.updated_at is not None
                else None
            ),
            course_code=meta.get(KEY_COURSE_CODE),
            programme=meta.get(KEY_PROGRAMME),
            semester=as_int(KEY_SEMESTER),
            section=meta.get(KEY_SECTION),
            session=meta.get(KEY_SESSION),
            credits=as_float(KEY_CREDITS),
            weekly_schedule=parse_schedule(meta.get(KEY_WEEKLY_SCHEDULE)),
            room=meta.get(KEY_ROOM),
            class_mode=meta.get(KEY_CLASS_MODE),
            notes=meta.get(KEY_NOTES),
            tags=list(parse_json_list(meta.get(KEY_TAGS))),
            student_count=student_count,
            links=links,
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class ListClassesResult:
    items: list[ClassOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Boundary DTOs — Enrollment (PART C)
# ---------------------------------------------------------------------------
@dataclass
class RosterEntry:
    """A denormalised enrolled student (roster row)."""

    student_id: str
    name: str
    roll_number: str | None
    email: str | None
    programme: str | None
    semester: int | None
    section: str | None
    student_type: str | None = None


@dataclass
class EnrollmentResult:
    """Outcome of a bulk enrollment (ids or CSV): what actually changed."""

    enrolled: list[str] = field(default_factory=list)
    already_enrolled: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Boundary DTOs — Assignment
# ---------------------------------------------------------------------------
@dataclass
class CreateAssignmentInput:
    title: str
    class_id: ObjectId
    created_by: str
    assignment_type: str = "assignment"
    description: str | None = None
    instructions: str | None = None
    max_marks: float | None = None
    deadline: str | None = None
    late_allowed: bool = False
    rubric: tuple[dict, ...] = ()
    visibility: str = "visible"
    weightage: float | None = None
    status: ObjectStatus = ObjectStatus.DRAFT


@dataclass
class UpdateAssignmentInput:
    actor: str
    title: str | None = None
    status: ObjectStatus | None = None
    assignment_type: str | None = None
    description: str | None = None
    instructions: str | None = None
    max_marks: float | None = None
    deadline: str | None = None
    late_allowed: bool | None = None
    rubric: tuple[dict, ...] | None = None
    visibility: str | None = None
    weightage: float | None = None


@dataclass
class AssignmentOutput:
    """Read-side projection of an Assignment Object."""

    id: str
    title: str
    class_id: str
    class_title: str | None
    assignment_type: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    description: str | None = None
    instructions: str | None = None
    max_marks: float | None = None
    deadline: str | None = None
    late_allowed: bool = False
    rubric: list[dict] = field(default_factory=list)
    visibility: str = "visible"
    weightage: float | None = None
    attachment_file_name: str | None = None
    attachment_file_size: int = 0
    attachment_mime_type: str | None = None
    attachment_file_path: str | None = None
    attachment_url: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        class_obj: UniversalObject | None = None,
        attachment_url: str | None = None,
    ) -> AssignmentOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        def as_float(key: str) -> float | None:
            raw = meta.get(key)
            try:
                return float(raw) if raw not in (None, "") else None
            except ValueError:
                return None

        class_ids = [
            str(r.target) for r in obj.relationships if r.kind is RelationshipKind.BELONGS_TO
        ]
        return AssignmentOutput(
            id=str(obj.id),
            title=obj.title,
            class_id=(class_ids[0] if class_ids else str(class_obj.id) if class_obj else ""),
            class_title=class_obj.title if class_obj else None,
            assignment_type=meta.get(KEY_ASSIGNMENT_TYPE) or "assignment",
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat()
                if obj.audit is not None and obj.audit.updated_at is not None
                else None
            ),
            description=meta.get(KEY_DESCRIPTION),
            instructions=meta.get(KEY_INSTRUCTIONS),
            max_marks=as_float(KEY_MAX_MARKS),
            deadline=meta.get(KEY_DEADLINE),
            late_allowed=parse_bool(meta.get(KEY_LATE_ALLOWED)),
            rubric=parse_rubric(meta.get(KEY_RUBRIC)),
            visibility=meta.get(KEY_VISIBILITY) or "visible",
            weightage=as_float(KEY_WEIGHTAGE),
            attachment_file_name=meta.get(KEY_ATTACHMENT_NAME),
            attachment_file_size=int(meta.get(KEY_ATTACHMENT_SIZE) or 0),
            attachment_mime_type=meta.get(KEY_ATTACHMENT_MIME),
            attachment_file_path=meta.get(KEY_ATTACHMENT_PATH),
            attachment_url=attachment_url,
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class ListAssignmentsResult:
    items: list[AssignmentOutput]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Boundary DTOs — Submission (+ the student × assignment grid)
# ---------------------------------------------------------------------------
@dataclass
class SubmissionOutput:
    """Read-side projection of a Submission Object."""

    id: str
    assignment_id: str
    student_id: str
    student_name: str | None
    student_roll: str | None
    submitted_at: str | None
    is_late: bool
    comments: str | None
    marks: float | None
    faculty_feedback: str | None
    rubric_score: list[dict]
    graded_at: str | None
    graded_by: str | None
    file_name: str | None
    file_size: int
    file_mime_type: str | None
    file_path: str | None
    file_url: str | None
    status: str
    version: int
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        student: UniversalObject | None = None,
        file_url: str | None = None,
    ) -> SubmissionOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        assignment_ids = [
            str(r.target) for r in obj.relationships if r.kind is RelationshipKind.BELONGS_TO
        ]
        student_ids = [
            str(r.target) for r in obj.relationships if r.kind is RelationshipKind.AUTHORED_BY
        ]
        raw_marks = meta.get(KEY_MARKS)
        try:
            marks = float(raw_marks) if raw_marks not in (None, "") else None
        except ValueError:
            marks = None

        student_meta = (
            {e.key: e.value for e in student.metadata.entries} if student is not None else {}
        )
        roll = student_meta.get("roll_number")

        rubric_score = []
        for entry in parse_json_list(meta.get(KEY_RUBRIC_SCORE)):
            if isinstance(entry, dict) and entry.get("criterion"):
                try:
                    awarded = float(entry.get("marks_awarded", 0) or 0)
                except (ValueError, TypeError):
                    awarded = 0.0
                rubric_score.append(
                    {"criterion": str(entry["criterion"]), "marks_awarded": awarded}
                )

        return SubmissionOutput(
            id=str(obj.id),
            assignment_id=(assignment_ids[0] if assignment_ids else ""),
            student_id=(student_ids[0] if student_ids else (str(student.id) if student else "")),
            student_name=student.title if student else None,
            student_roll=roll,
            submitted_at=meta.get(KEY_SUBMITTED_AT),
            is_late=parse_bool(meta.get(KEY_IS_LATE)),
            comments=meta.get(KEY_COMMENTS),
            marks=marks,
            faculty_feedback=meta.get(KEY_FACULTY_FEEDBACK),
            rubric_score=rubric_score,
            graded_at=meta.get(KEY_GRADED_AT),
            graded_by=meta.get(KEY_GRADED_BY),
            file_name=meta.get(KEY_FILE_NAME),
            file_size=int(meta.get(KEY_FILE_SIZE) or 0),
            file_mime_type=meta.get(KEY_FILE_MIME),
            file_path=meta.get(KEY_FILE_PATH),
            file_url=file_url,
            status=obj.status.value,
            version=obj.version,
            metadata=meta,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class SubmissionGridRow:
    """One roster row of the student × assignment matrix (UI Spec §2.5 C7).

    ``state``: submitted | late | pending | graded (+ late+graded overlay).
    A pending row is virtual — no Submission Object exists yet.
    """

    student_id: str
    student_name: str
    student_roll: str | None
    state: str
    submission: SubmissionOutput | None = None


@dataclass
class SubmissionGrid:
    assignment_id: str
    rows: list[SubmissionGridRow]
    submitted_count: int
    late_count: int
    pending_count: int
    graded_count: int


# ---------------------------------------------------------------------------
# Boundary DTOs — Attendance (PART I)
# ---------------------------------------------------------------------------
@dataclass
class AttendanceSessionOutput:
    id: str
    class_id: str
    session_date: str
    records: dict[str, str]  # student_id -> state
    status: str
    version: int
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(obj: UniversalObject, events: list) -> AttendanceSessionOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        class_ids = [
            str(r.target) for r in obj.relationships if r.kind is RelationshipKind.BELONGS_TO
        ]
        return AttendanceSessionOutput(
            id=str(obj.id),
            class_id=(class_ids[0] if class_ids else ""),
            session_date=meta.get(KEY_SESSION_DATE) or "",
            records=parse_json_object(meta.get(KEY_ATTENDANCE_RECORDS)),
            status=obj.status.value,
            version=obj.version,
            events=[type(event).__name__ for event in events],
        )


@dataclass
class AttendanceSummaryRow:
    student_id: str
    student_name: str
    student_roll: str | None
    present: int
    absent: int
    late: int
    medical_leave: int
    effective_present: int  # present + late + medical_leave
    total: int
    percentage: float  # effective_present / total * 100
    below_threshold: bool  # < threshold (default 75%, university norm)


@dataclass
class AttendanceSummary:
    class_id: str
    session_count: int
    threshold: float
    rows: list[AttendanceSummaryRow]


# ---------------------------------------------------------------------------
# Boundary DTOs — Gradebook / Class report / Dashboard (PARTS H, J, K)
# ---------------------------------------------------------------------------
@dataclass
class GradebookCell:
    assignment_id: str
    title: str
    assignment_type: str
    max_marks: float | None
    weightage: float | None
    marks: float | None  # None = not submitted / not graded
    is_late: bool


@dataclass
class GradebookRow:
    student_id: str
    student_name: str
    student_roll: str | None
    cells: list[GradebookCell]
    internal_total: float  # weighted internal assessment total (0-100 scale)
    internal_max: float  # achieved weightage covered so far
    grade: str  # computed from internal_total + end_semester contribution
    average_percent: float


@dataclass
class Gradebook:
    class_id: str
    assignments: list[dict]  # header: id, title, type, max_marks, weightage
    rows: list[GradebookRow]


@dataclass
class AssignmentStat:
    assignment_id: str
    title: str
    assignment_type: str
    max_marks: float | None
    deadline: str | None
    submitted: int
    late: int
    pending: int
    graded: int
    average_marks: float | None


@dataclass
class ClassReport:
    """The structured "Class Report" payload (PART K) — future AI-ready.

    One call returns everything a report generator needs for a class:
    identity, roster, per-assignment stats, the gradebook, attendance
    summary and the derived cohort signals (weak students, toppers).
    """

    class_info: ClassOutput
    roster: list[RosterEntry]
    assignment_stats: list[AssignmentStat]
    gradebook: Gradebook
    attendance: AttendanceSummary
    average_marks_percent: float | None
    pending_submissions: int
    late_submissions: int
    weak_students: list[dict]  # below marks OR attendance threshold
    top_performers: list[dict]


@dataclass
class TeachingDashboard:
    """Faculty dashboard aggregates (PART J) across all active classes."""

    class_count: int
    student_count: int  # distinct enrolled students
    assignment_count: int
    pending_submissions: int
    late_submissions: int
    graded_submissions: int
    average_marks_percent: float | None
    weak_students: list[dict]  # up to 10
    top_performers: list[dict]  # up to 10
    classes: list[ClassOutput]


@dataclass
class ListSubmissionsResult:
    items: list[SubmissionOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class MarksImportResult:
    """Outcome of an assignment-marks CSV import (PARTS F + G).

    Rows resolve students through the class roster (roll number first, then
    name — the auto-mapping contract); a missing Submission Object is
    created on the fly so Google-Form exports land whole.
    """

    assignment_id: str
    graded: list[str] = field(default_factory=list)  # submission ids written
    created_submissions: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


@dataclass
class AttendanceImportResult:
    """Outcome of an attendance CSV import (PART I: CSV + manual entry)."""

    class_id: str
    session_date: str
    applied: list[str] = field(default_factory=list)  # student ids recorded
    unknown: list[dict] = field(default_factory=list)  # rows with no roster match
    errors: list[dict] = field(default_factory=list)
