"""Use case: the computed Gradebook of a Class (PART H).

Weightage model (documented, deterministic):

  * every graded cell has ``pct = marks / max_marks * 100`` (cells whose
    assignment has no max marks contribute marks but no percent);
  * a cell's weight ``w`` is the assignment's ``weightage`` when given,
    else its ``max_marks`` (marks-weighted), else 1;
  * ``internal_total`` = weighted mean of pcts over INTERNAL_TYPES
    (assignment / quiz / internal assessment / mid semester);
  * ``average_percent`` = weighted mean over every pct-able graded cell
    (internal + end semester — the automatic total, 0–100);
  * ``grade`` = letter band of ``average_percent`` (GRADE_BANDS);
  * ``internal_max`` = the internal weight actually covered by graded
    cells, so faculty see "grading progress" at a glance.

Everything is COMPUTED from Assignment + Submission + roster via the frozen
interface — ``build_gradebook`` is the shared builder the class report and
dashboard reuse.
"""
from __future__ import annotations

from app.application.dtos.teaching import (
    INTERNAL_TYPES,
    KEY_ASSIGNMENT_TYPE,
    KEY_MAX_MARKS,
    KEY_WEIGHTAGE,
    Gradebook,
    GradebookCell,
    GradebookRow,
    SubmissionOutput,
    grade_for,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_gradebook import GetGradebookQuery
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    enrolled_students,
    student_of_submission,
    submissions_of_assignment,
    to_roster_entry,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _as_float(raw) -> float | None:
    try:
        return float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _weight(assignment: UniversalObject, max_marks: float | None) -> float:
    weightage = _as_float(assignment.metadata.get_value(KEY_WEIGHTAGE))
    if weightage is not None:
        return weightage
    if max_marks:
        return max_marks
    return 1.0


def build_gradebook(
    roster: list[UniversalObject],
    assignments: list[UniversalObject],
    submissions_by_assignment: dict[str, dict[str, SubmissionOutput]],
    *,
    class_id: str,
) -> Gradebook:
    headers = []
    for assignment in assignments:
        max_marks = _as_float(assignment.metadata.get_value(KEY_MAX_MARKS))
        headers.append(
            {
                "id": str(assignment.id),
                "title": assignment.title,
                "assignment_type": assignment.metadata.get_value(KEY_ASSIGNMENT_TYPE)
                or "assignment",
                "max_marks": max_marks,
                "weightage": _as_float(assignment.metadata.get_value(KEY_WEIGHTAGE)),
            }
        )

    rows: list[GradebookRow] = []
    for student in roster:
        entry = to_roster_entry(student)
        sid = str(student.id)
        cells: list[GradebookCell] = []
        internal_num = internal_den = overall_num = overall_den = 0.0
        for assignment in assignments:
            max_marks = _as_float(assignment.metadata.get_value(KEY_MAX_MARKS))
            kind = assignment.metadata.get_value(KEY_ASSIGNMENT_TYPE) or "assignment"
            sub = submissions_by_assignment.get(str(assignment.id), {}).get(sid)
            marks = sub.marks if sub is not None else None
            cells.append(
                GradebookCell(
                    assignment_id=str(assignment.id),
                    title=assignment.title,
                    assignment_type=kind,
                    max_marks=max_marks,
                    weightage=_as_float(assignment.metadata.get_value(KEY_WEIGHTAGE)),
                    marks=marks,
                    is_late=bool(sub.is_late) if sub is not None else False,
                )
            )
            if marks is None or not max_marks:
                continue
            pct = (marks / max_marks) * 100
            w = _weight(assignment, max_marks)
            overall_num += w * pct
            overall_den += w
            if kind in INTERNAL_TYPES:
                internal_num += w * pct
                internal_den += w

        internal_total = round(internal_num / internal_den, 2) if internal_den else 0.0
        average = round(overall_num / overall_den, 2) if overall_den else 0.0
        rows.append(
            GradebookRow(
                student_id=sid,
                student_name=entry.name,
                student_roll=entry.roll_number,
                cells=cells,
                internal_total=internal_total,
                internal_max=round(internal_den, 2),
                grade=grade_for(average),
                average_percent=average,
            )
        )
    rows.sort(key=lambda r: ((r.student_roll or "￿").casefold(), r.student_name.casefold()))
    return Gradebook(class_id=class_id, assignments=headers, rows=rows)


def collect_submissions(
    repository: ObjectRepository, assignments: list[UniversalObject]
) -> dict[str, dict[str, SubmissionOutput]]:
    """{assignment_id: {student_id: SubmissionOutput}} in one pass."""
    out: dict[str, dict[str, SubmissionOutput]] = {}
    students_cache: dict[str, UniversalObject] = {}
    for assignment in assignments:
        by_student: dict[str, SubmissionOutput] = {}
        for submission in submissions_of_assignment(repository, str(assignment.id)):
            sid = student_of_submission(submission)
            if sid is None:
                continue
            key = str(sid)
            if key not in students_cache:
                student = repository.get_by_id(sid)
                if student is not None:
                    students_cache[key] = student
            by_student[key] = SubmissionOutput.from_domain(
                submission, [], student=students_cache.get(key)
            )
        out[str(assignment.id)] = by_student
    return out


class GetGradebookUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetGradebookQuery) -> Gradebook:
        cls = self._repository.get_by_id(query.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.class_id} not found.")
        roster = enrolled_students(self._repository, str(cls.id))
        assignments = assignments_of_class(self._repository, str(cls.id))
        assignments.sort(
            key=lambda a: (a.metadata.get_value("deadline") or "￿", a.title.casefold())
        )
        submissions = collect_submissions(self._repository, assignments)
        return build_gradebook(roster, assignments, submissions, class_id=str(cls.id))
