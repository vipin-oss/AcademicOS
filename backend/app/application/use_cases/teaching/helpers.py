"""Shared read helpers for the Teaching use cases.

Every aggregate view (roster, submission grid, gradebook, report, dashboard)
reads through these — one place that knows how the object graph answers
teaching questions via the FROZEN repository interface (find_by_type +
relationship edges; the same portable pattern the publication lenses use).
"""
from __future__ import annotations

from app.application.dtos.student import KEY_ROLL_NUMBER
from app.application.dtos.teaching import RosterEntry
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


def enrolled_students(
    repository: ObjectRepository, class_id: str, *, owner_user_id: str | None = None
) -> list[UniversalObject]:
    """Students whose Object carries an ENROLLED_IN edge to ``class_id``.

    Security correction + perf hardening (Phase 2B audit follow-up):
    previously called find_by_type(STUDENT) with no owner_user_id at all.
    For single-class callers (the majority — one class per request) this
    is a straightforward scoping fix. For callers resolving rosters
    across MANY classes in one request (list_classes, teaching/analytics
    reports), use ``students_by_class`` instead — it does one scan and
    groups by class, rather than one full STUDENT-table scan per class.
    """
    return [
        student
        for student in repository.find_by_type(ObjectType.STUDENT, owner_user_id=owner_user_id)
        if class_id in {str(oid) for oid in student.related_ids(RelationshipKind.ENROLLED_IN)}
    ]


def students_by_class(
    repository: ObjectRepository,
    class_ids: list[str],
    *,
    owner_user_id: str | None = None,
) -> dict[str, list[UniversalObject]]:
    """The same ENROLLED_IN grouping as ``enrolled_students``, computed for
    MANY classes from a single STUDENT scan.

    Perf hardening (Phase 2B audit follow-up): list_classes.py (and any
    future multi-class report) should use this instead of calling
    ``enrolled_students`` once per class — that pattern was measured to
    trigger one full STUDENT-table scan per class on the page (a 20-class
    page = 20 scans), the exact N+1 shape the audit's sweep found.
    """
    wanted = set(class_ids)
    result: dict[str, list[UniversalObject]] = {cid: [] for cid in wanted}
    for student in repository.find_by_type(ObjectType.STUDENT, owner_user_id=owner_user_id):
        for cid in {str(oid) for oid in student.related_ids(RelationshipKind.ENROLLED_IN)} & wanted:
            result[cid].append(student)
    return result


def to_roster_entry(student: UniversalObject) -> RosterEntry:
    meta = {entry.key: entry.value for entry in student.metadata.entries}
    try:
        semester = int(meta.get("semester") or "") if meta.get("semester") else None
    except ValueError:
        semester = None
    return RosterEntry(
        student_id=str(student.id),
        name=student.title,
        roll_number=meta.get(KEY_ROLL_NUMBER),
        email=meta.get("email"),
        programme=meta.get("programme"),
        semester=semester,
        section=meta.get("section"),
        student_type=meta.get("student_type"),
    )


def class_of(repository: ObjectRepository, class_id: ObjectId) -> UniversalObject:
    """The Class Object or ``None``-safety helper (callers raise their 404)."""
    obj = repository.get_by_id(class_id)
    if obj is None or obj.object_type is not ObjectType.COURSE:
        return None
    return obj


def assignments_of_class(repository: ObjectRepository, class_id: str) -> list[UniversalObject]:
    """Assignments BELONGS_TO the class."""
    return [
        assignment
        for assignment in repository.find_by_type(ObjectType.ASSIGNMENT)
        if class_id
        in {str(oid) for oid in assignment.related_ids(RelationshipKind.BELONGS_TO)}
    ]


def assignment_of(repository: ObjectRepository, assignment_id: ObjectId) -> UniversalObject | None:
    obj = repository.get_by_id(assignment_id)
    if obj is None or obj.object_type is not ObjectType.ASSIGNMENT:
        return None
    return obj


def class_id_of_assignment(assignment: UniversalObject) -> str | None:
    ids = assignment.related_ids(RelationshipKind.BELONGS_TO)
    return str(ids[0]) if ids else None


def submission_for(
    repository: ObjectRepository, assignment_id: str, student_id: str
) -> UniversalObject | None:
    """The single Submission Object of (assignment, student), if any."""
    for submission in repository.find_by_type(ObjectType.SUBMISSION):
        if (
            assignment_id
            in {str(oid) for oid in submission.related_ids(RelationshipKind.BELONGS_TO)}
            and student_id
            in {str(oid) for oid in submission.related_ids(RelationshipKind.AUTHORED_BY)}
        ):
            return submission
    return None


def submissions_of_assignment(repository: ObjectRepository, assignment_id: str) -> list[UniversalObject]:
    return [
        submission
        for submission in repository.find_by_type(ObjectType.SUBMISSION)
        if assignment_id
        in {str(oid) for oid in submission.related_ids(RelationshipKind.BELONGS_TO)}
    ]


def student_of_submission(submission: UniversalObject) -> ObjectId | None:
    ids = submission.related_ids(RelationshipKind.AUTHORED_BY)
    return ids[0] if ids else None


def attendance_sessions_of_class(
    repository: ObjectRepository, class_id: str
) -> list[UniversalObject]:
    return [
        session
        for session in repository.find_by_type(ObjectType.ATTENDANCE_SESSION)
        if class_id in {str(oid) for oid in session.related_ids(RelationshipKind.BELONGS_TO)}
    ]
