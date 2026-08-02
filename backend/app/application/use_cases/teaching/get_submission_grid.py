"""Use case: The student × assignment submission grid (UI Spec §2.5 C7).

Every roster row of the assignment's class appears exactly once —
``pending`` rows are virtual (no Submission Object yet) so the faculty
always sees the whole class at a glance. Counts answer PART J directly:
submitted / late / pending / graded.
"""
from __future__ import annotations

from app.application.dtos.teaching import (
    SubmissionGrid,
    SubmissionGridRow,
    SubmissionOutput,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_submission_grid import GetSubmissionGridQuery
from app.application.use_cases.teaching.helpers import (
    class_id_of_assignment,
    enrolled_students,
    student_of_submission,
    submissions_of_assignment,
    to_roster_entry,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetSubmissionGridUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetSubmissionGridQuery) -> SubmissionGrid:
        assignment = self._repository.get_by_id(query.assignment_id)
        if assignment is None or assignment.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {query.assignment_id} not found.")

        class_id = class_id_of_assignment(assignment)
        roster = (
            enrolled_students(self._repository, class_id) if class_id is not None else []
        )
        roster.sort(key=lambda s: ((s.metadata.get_value("roll_number") or "￿").casefold(),
                                   s.title.casefold()))

        submissions = submissions_of_assignment(self._repository, str(assignment.id))
        by_student: dict[str, SubmissionOutput] = {}
        for submission in submissions:
            sid = student_of_submission(submission)
            if sid is None:
                continue
            student = self._repository.get_by_id(sid)
            by_student[str(sid)] = SubmissionOutput.from_domain(
                submission, [], student=student
            )

        rows: list[SubmissionGridRow] = []
        submitted = late = graded = 0
        for student in roster:
            entry = to_roster_entry(student)
            sub = by_student.get(str(student.id))
            if sub is None:
                state = "pending"
            elif sub.marks is not None:
                state = "graded"
                graded += 1
            elif sub.is_late:
                state = "late"
                late += 1
            else:
                state = "submitted"
                submitted += 1
            rows.append(
                SubmissionGridRow(
                    student_id=entry.student_id,
                    student_name=entry.name,
                    student_roll=entry.roll_number,
                    state=state,
                    submission=sub,
                )
            )

        pending = len(roster) - submitted - late - graded
        return SubmissionGrid(
            assignment_id=str(assignment.id),
            rows=rows,
            submitted_count=submitted,
            late_count=late,
            pending_count=max(pending, 0),
            graded_count=graded,
        )
