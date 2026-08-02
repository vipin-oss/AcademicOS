"""Use case: the faculty Teaching dashboard (PART J).

Aggregates, across EVERY class, the numbers the spec names — classes,
students (distinct, by roster), assignments, pending submissions, late
submissions, average marks, weak students, top performers — computed from
the same objects through the shared builders, so the dashboard never
disagrees with the class report.
"""
from __future__ import annotations

from app.application.dtos.teaching import ClassOutput, TeachingDashboard
from app.application.queries.get_teaching_dashboard import GetTeachingDashboardQuery
from app.application.use_cases.teaching.attendance_summary import (
    build_attendance_summary,
)
from app.application.use_cases.teaching.get_class_report import weak_and_top
from app.application.use_cases.teaching.get_gradebook import (
    build_gradebook,
    collect_submissions,
)
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    attendance_sessions_of_class,
    enrolled_students,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType

_TOP_N = 10


class GetTeachingDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetTeachingDashboardQuery) -> TeachingDashboard:
        classes = sorted(
            self._repository.find_by_type(ObjectType.COURSE),
            key=lambda c: (c.title.casefold(), str(c.id)),
        )

        student_ids: set[str] = set()
        assignment_count = 0
        pending = late = graded = 0
        averages: list[float] = []
        weak_all: list[dict] = []
        top_all: list[dict] = []
        class_outputs: list[ClassOutput] = []

        for cls in classes:
            class_id = str(cls.id)
            roster = enrolled_students(self._repository, class_id)
            student_ids.update(str(s.id) for s in roster)
            assignments = assignments_of_class(self._repository, class_id)
            assignment_count += len(assignments)

            submissions = collect_submissions(self._repository, assignments)
            for assignment in assignments:
                by_student = submissions.get(str(assignment.id), {})
                pending += max(len(roster) - len(by_student), 0)
                late += sum(1 for s in by_student.values() if s.is_late)
                graded += sum(1 for s in by_student.values() if s.marks is not None)

            gradebook = build_gradebook(roster, assignments, submissions, class_id=class_id)
            sessions = attendance_sessions_of_class(self._repository, class_id)
            attendance = build_attendance_summary(
                roster, sessions, class_id=class_id, threshold=query.attendance_threshold
            )
            for row in gradebook.rows:
                if any(c.marks is not None for c in row.cells):
                    averages.append(row.average_percent)
            weak, top = weak_and_top(
                gradebook, attendance, class_id=class_id, class_title=cls.title
            )
            weak_all.extend(weak)
            top_all.extend(top)

            linked_by_id = {
                str(o.id): o
                for o in self._repository.find_by_ids([r.target for r in cls.relationships])
            }
            class_outputs.append(
                ClassOutput.from_domain(
                    cls, [], linked_by_id=linked_by_id, student_count=len(roster)
                )
            )

        weak_all.sort(key=lambda e: (e["average_marks_percent"], e["name"].casefold()))
        top_all.sort(key=lambda e: (-e["average_marks_percent"], e["name"].casefold()))

        return TeachingDashboard(
            class_count=len(classes),
            student_count=len(student_ids),
            assignment_count=assignment_count,
            pending_submissions=pending,
            late_submissions=late,
            graded_submissions=graded,
            average_marks_percent=(
                round(sum(averages) / len(averages), 2) if averages else None
            ),
            weak_students=weak_all[:_TOP_N],
            top_performers=top_all[:_TOP_N],
            classes=class_outputs[:100],
        )
