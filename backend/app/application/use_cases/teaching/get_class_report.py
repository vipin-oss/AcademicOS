"""Use case: the AI-report-ready Class Report (PART K).

One call composes everything a report generator needs for a class —
identity, roster, per-assignment stats, the gradebook, the attendance
summary and the derived cohort signals (weak students / top performers) —
all from the same objects through the shared builders (no shadow maths).

Signals (documented thresholds):
  * weak student: graded average below 40% OR attendance below the
    threshold (default 75%) — reasons are listed explicitly;
  * top performer: graded average at or above 85%.
"""
from __future__ import annotations

from app.application.dtos.teaching import (
    AssignmentStat,
    ClassOutput,
    ClassReport,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_class_report import GetClassReportQuery
from app.application.use_cases.teaching.attendance_summary import (
    build_attendance_summary,
)
from app.application.use_cases.teaching.get_gradebook import (
    build_gradebook,
    collect_submissions,
)
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    attendance_sessions_of_class,
    enrolled_students,
    to_roster_entry,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType

WEAK_MARKS_THRESHOLD = 40.0
TOP_MARKS_THRESHOLD = 85.0


def _assignment_stats(
    assignments, roster_size: int, submissions_by_assignment
) -> list[AssignmentStat]:
    stats = []
    for assignment in assignments:
        by_student = submissions_by_assignment.get(str(assignment.id), {})
        submitted = sum(1 for s in by_student.values() if s.submitted_at)
        late = sum(1 for s in by_student.values() if s.is_late)
        graded_marks = [s.marks for s in by_student.values() if s.marks is not None]
        stats.append(
            AssignmentStat(
                assignment_id=str(assignment.id),
                title=assignment.title,
                assignment_type=assignment.metadata.get_value("assignment_type")
                or "assignment",
                max_marks=_as_float(assignment.metadata.get_value("max_marks")),
                deadline=assignment.metadata.get_value("deadline"),
                submitted=submitted,
                late=late,
                pending=max(roster_size - len(by_student), 0),
                graded=len(graded_marks),
                average_marks=(
                    round(sum(graded_marks) / len(graded_marks), 2) if graded_marks else None
                ),
            )
        )
    return stats


def _as_float(raw) -> float | None:
    try:
        return float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def weak_and_top(
    gradebook, attendance, *, class_id: str = "", class_title: str = ""
) -> tuple[list[dict], list[dict]]:
    """Shared cohort signals (class report + dashboard reuse them)."""
    attendance_by_id = {row.student_id: row for row in attendance.rows}
    weak: list[dict] = []
    top: list[dict] = []
    for row in gradebook.rows:
        att = attendance_by_id.get(row.student_id)
        attendance_pct = att.percentage if att is not None else None
        attendance_flag = bool(att.below_threshold) if att is not None else False
        has_grades = any(cell.marks is not None for cell in row.cells)
        entry = {
            "student_id": row.student_id,
            "name": row.student_name,
            "roll_number": row.student_roll,
            "average_marks_percent": row.average_percent,
            "attendance_percent": attendance_pct,
        }
        if class_id:
            entry["class_id"] = class_id
            entry["class_title"] = class_title
        reasons = []
        if has_grades and row.average_percent < WEAK_MARKS_THRESHOLD:
            reasons.append(f"average marks below {WEAK_MARKS_THRESHOLD:g}%")
        if attendance_flag:
            reasons.append("attendance below threshold")
        if reasons:
            entry["reasons"] = reasons
            weak.append(entry)
        elif has_grades and row.average_percent >= TOP_MARKS_THRESHOLD:
            top.append(entry)
    weak.sort(key=lambda e: (e["average_marks_percent"], e["name"].casefold()))
    top.sort(key=lambda e: (-e["average_marks_percent"], e["name"].casefold()))
    return weak, top


class GetClassReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetClassReportQuery) -> ClassReport:
        cls = self._repository.get_by_id(query.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.class_id} not found.")

        class_id = str(cls.id)
        roster = enrolled_students(self._repository, class_id)
        roster_entries = [to_roster_entry(s) for s in roster]
        roster_entries.sort(
            key=lambda e: ((e.roll_number or "￿").casefold(), e.name.casefold())
        )
        assignments = assignments_of_class(self._repository, class_id)
        assignments.sort(
            key=lambda a: (a.metadata.get_value("deadline") or "￿", a.title.casefold())
        )
        submissions = collect_submissions(self._repository, assignments)
        gradebook = build_gradebook(roster, assignments, submissions, class_id=class_id)

        sessions = attendance_sessions_of_class(self._repository, class_id)
        sessions.sort(key=lambda s: (s.metadata.get_value("session_date") or "", str(s.id)))
        attendance = build_attendance_summary(
            roster, sessions, class_id=class_id, threshold=query.attendance_threshold
        )

        stats = _assignment_stats(assignments, len(roster), submissions)
        graded_rows = [r for r in gradebook.rows if any(c.marks is not None for c in r.cells)]
        average_marks = (
            round(sum(r.average_percent for r in graded_rows) / len(graded_rows), 2)
            if graded_rows
            else None
        )
        weak, top = weak_and_top(
            gradebook, attendance, class_id=class_id, class_title=cls.title
        )

        linked_by_id = {
            str(o.id): o
            for o in self._repository.find_by_ids([r.target for r in cls.relationships])
        }
        return ClassReport(
            class_info=ClassOutput.from_domain(
                cls, [], linked_by_id=linked_by_id, student_count=len(roster)
            ),
            roster=roster_entries,
            assignment_stats=stats,
            gradebook=gradebook,
            attendance=attendance,
            average_marks_percent=average_marks,
            pending_submissions=sum(s.pending for s in stats),
            late_submissions=sum(s.late for s in stats),
            weak_students=weak[:10],
            top_performers=top[:10],
        )
