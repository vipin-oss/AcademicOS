"""Use case: Grade a Submission (marks / feedback / rubric breakdown — PARTS E+H).

Grading facts are human-asserted (marks, feedback, rubric scores, grader —
L6) with a system grading timestamp (L1). The marks ceiling is enforced
against the OWNING assignment's max marks, so a grade can never exceed the
assessment it belongs to.
"""
from __future__ import annotations

import datetime as dt

from app.application.commands.grade_submission import GradeSubmissionCommand
from app.application.dtos.teaching import (
    KEY_FACULTY_FEEDBACK,
    KEY_GRADED_AT,
    KEY_GRADED_BY,
    KEY_MARKS,
    KEY_MAX_MARKS,
    KEY_RUBRIC_SCORE,
    SubmissionOutput,
    encode_json,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.teaching.helpers import student_of_submission
from app.application.validators.teaching import validate_marks_value
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


class GradeSubmissionUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: GradeSubmissionCommand) -> SubmissionOutput:
        submission = self._repository.get_by_id(command.object_id)
        if submission is None or submission.object_type is not ObjectType.SUBMISSION:
            raise ObjectNotFoundError(f"Submission {command.object_id} not found.")

        actor = (command.actor or "system").strip() or "system"
        if not actor:
            raise ValidationError("actor must identify who grades.")

        assignment_ids = submission.related_ids(RelationshipKind.BELONGS_TO)
        assignment = (
            self._repository.get_by_id(assignment_ids[0]) if assignment_ids else None
        )
        max_marks = None
        if assignment is not None:
            raw_max = assignment.metadata.get_value(KEY_MAX_MARKS)
            try:
                max_marks = float(raw_max) if raw_max not in (None, "") else None
            except ValueError:
                max_marks = None

        def asserted(key: str, value: str) -> None:
            if submission.metadata.get_value(key) != value:
                submission.set_metadata(
                    MetadataEntry(
                        key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                    ),
                    actor=actor,
                )

        graded = False
        if command.marks is not None:
            errors = validate_marks_value(command.marks, max_marks)
            if errors:
                raise ValidationError("; ".join(errors))
            asserted(KEY_MARKS, str(command.marks))
            graded = True
        if command.faculty_feedback is not None:
            asserted(KEY_FACULTY_FEEDBACK, command.faculty_feedback)
        if command.rubric_score is not None:
            total = 0.0
            for entry in command.rubric_score:
                try:
                    total += float(entry.get("marks_awarded", 0) or 0)
                except (TypeError, ValueError, AttributeError):
                    raise ValidationError("rubric_score entries need numeric marks_awarded.")
            asserted(KEY_RUBRIC_SCORE, encode_json(list(command.rubric_score)))
            if command.marks is None:  # rubric total becomes the marks
                errors = validate_marks_value(total, max_marks)
                if errors:
                    raise ValidationError(
                        "Rubric total exceeds the assignment maximum: " + "; ".join(errors)
                    )
                asserted(KEY_MARKS, str(total))
                graded = True

        if not graded and command.faculty_feedback is None and command.rubric_score is None:
            raise ValidationError("Nothing to grade: provide marks, rubric_score or feedback.")

        if graded:
            asserted(KEY_GRADED_BY, actor)
            now = dt.datetime.now(dt.UTC).isoformat()
            if submission.metadata.get_value(KEY_GRADED_AT) != now:
                submission.set_metadata(
                    MetadataEntry(
                        KEY_GRADED_AT, now, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM
                    ),
                    actor=actor,
                )

        self._repository.save(submission)
        events = submission.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        student_id = student_of_submission(submission)
        student = self._repository.get_by_id(student_id) if student_id is not None else None
        return SubmissionOutput.from_domain(submission, events, student=student)
