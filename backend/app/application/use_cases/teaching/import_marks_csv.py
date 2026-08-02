"""Use case: Import assignment marks from CSV (PARTS F + G — Google-Forms loop).

The CSV (Roll No, Marks, optional Feedback — headers auto-mapped) lands on
the class roster: each row resolves a student (roll number first, name
fallback), a missing Submission Object is created on the fly (one per
assignment × student, same write path as uploads), and grading itself is
delegated to ``GradeSubmissionUseCase`` so the max-marks ceiling and the
grading audit live in exactly one place. Bad rows are reported; good rows
still import.
"""
from __future__ import annotations

from app.application.commands.grade_submission import GradeSubmissionCommand
from app.application.commands.import_marks_csv import ImportMarksCsvCommand
from app.application.dtos.teaching import MarksImportResult
from app.application.exceptions import ApplicationError, ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.services import teaching_csv
from app.application.use_cases.teaching.grade_submission import GradeSubmissionUseCase
from app.application.use_cases.teaching.helpers import (
    class_id_of_assignment,
    enrolled_students,
    submission_for,
)
from app.application.validators.teaching import validate_marks_value
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)


class ImportMarksCsvUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: ImportMarksCsvCommand) -> MarksImportResult:
        assignment = self._repository.get_by_id(command.assignment_id)
        if assignment is None or assignment.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {command.assignment_id} not found.")
        if not command.text or not command.text.strip():
            raise ValidationError("Nothing to import: the CSV text is empty.")

        rows = teaching_csv.parse_marks_csv(command.text)
        if not rows:
            raise ValidationError(
                "No marks rows found — the first CSV row must be a header "
                "(Roll No, Marks, …)."
            )

        actor = (command.actor or "system").strip() or "system"
        raw_max = assignment.metadata.get_value("max_marks")
        try:
            max_marks = float(raw_max) if raw_max not in (None, "") else None
        except ValueError:
            max_marks = None
        class_id = class_id_of_assignment(assignment)
        roster = enrolled_students(self._repository, class_id) if class_id else []
        by_name = {s.title.strip().casefold(): s for s in roster}
        result = MarksImportResult(assignment_id=str(assignment.id))

        for index, record in enumerate(rows):
            roll = (record.get("roll_number") or "").strip()
            name = (record.get("name") or "").strip()
            student = _resolve(roster, roll) or by_name.get(name.casefold())
            if student is None:
                result.errors.append(
                    {
                        "index": index,
                        "roll_number": roll,
                        "name": name,
                        "message": "No enrolled student matches this row; skipped.",
                    }
                )
                continue
            raw_marks = (record.get("marks") or "").strip()
            try:
                marks = float(raw_marks)
            except ValueError:
                result.errors.append(
                    {
                        "index": index,
                        "roll_number": roll,
                        "message": f"marks must be a number (got {raw_marks!r}); skipped.",
                    }
                )
                continue
            bound_errors = validate_marks_value(marks, max_marks)
            if bound_errors:  # never materialise a submission for an invalid row
                result.errors.append(
                    {"index": index, "roll_number": roll, "message": "; ".join(bound_errors)}
                )
                continue

            submission = submission_for(self._repository, str(assignment.id), str(student.id))
            if submission is None:
                submission = UniversalObject.create(
                    object_type=ObjectType.SUBMISSION,
                    title=f"Submission: {student.title} → {assignment.title}",
                    created_by=actor,
                    status=ObjectStatus.ACTIVE,
                )
                submission.add_relationship(
                    assignment.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
                )
                submission.add_relationship(
                    student.id, RelationshipKind.AUTHORED_BY, Provenance.ASSERTED, actor=actor
                )
                self._repository.save(submission)
                submission.pop_domain_events()
                result.created_submissions.append(str(submission.id))

            try:
                GradeSubmissionUseCase(self._repository, self._event_publisher).execute(
                    GradeSubmissionCommand(
                        object_id=submission.id,
                        marks=marks,
                        faculty_feedback=record.get("feedback") or None,
                        actor=actor,
                    )
                )
                result.graded.append(str(submission.id))
            except ApplicationError as exc:  # per-row report, keep importing
                result.errors.append(
                    {"index": index, "roll_number": roll, "message": str(exc)}
                )
        return result


def _resolve(roster, roll: str):
    if not roll:
        return None
    key = roll.casefold()
    for student in roster:
        if (student.metadata.get_value("roll_number") or "").strip().casefold() == key:
            return student
    return None
