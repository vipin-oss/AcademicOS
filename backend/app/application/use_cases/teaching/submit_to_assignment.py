"""Use case: Record (or resubmit) a student's Submission (PART E).

ONE Submission Object per (assignment × student): resubmitting uploads the
new file onto the SAME object — the aggregate version IS the version
history. ``submitted_at`` is a system timestamp (L1), ``is_late`` is
computed against the deadline (L5 inferred); the student's comments are
L6 human-asserted. Late policy: when the assignment disallows late
submissions, an on-time check happens here and a late attempt is a
validation error, not silent data.
"""
from __future__ import annotations

import datetime as dt
import re

from app.application.commands.submit_to_assignment import SubmitToAssignmentCommand
from app.application.dtos.teaching import (
    KEY_COMMENTS,
    KEY_DEADLINE,
    KEY_FILE_MIME,
    KEY_FILE_NAME,
    KEY_FILE_PATH,
    KEY_FILE_SIZE,
    KEY_IS_LATE,
    KEY_LATE_ALLOWED,
    KEY_SUBMITTED_AT,
    SubmissionOutput,
    parse_bool,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.teaching.helpers import submission_for
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(part: str) -> str:
    return _SAFE_CHARS.sub("_", part).strip("._") or "unnamed"


def _parse_deadline(raw: str | None) -> dt.datetime | None:
    """Deadline as an aware UTC datetime; a bare date closes at end of day."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if isinstance(value, dt.datetime):
        if value.hour == 0 and value.minute == 0 and "T" not in raw and " " not in raw:
            value = value.replace(hour=23, minute=59, second=59)
    else:  # date only
        value = dt.datetime(value.year, value.month, value.day, 23, 59, 59)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value


def _parse_moment(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        value = dt.datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if not isinstance(value, dt.datetime):
        value = dt.datetime(value.year, value.month, value.day)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value


class SubmitToAssignmentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._event_publisher = event_publisher

    def execute(self, command: SubmitToAssignmentCommand) -> SubmissionOutput:
        assignment = self._repository.get_by_id(command.assignment_id)
        if assignment is None or assignment.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {command.assignment_id} not found.")
        student = self._repository.get_by_id(command.student_id)
        if student is None or student.object_type is not ObjectType.STUDENT:
            raise ObjectNotFoundError(f"Student {command.student_id} not found.")
        if command.content is not None and not command.content:
            raise ValidationError("The uploaded file is empty.")
        if command.content is not None and not (command.file_name or "").strip():
            raise ValidationError("file_name is required when a file is uploaded.")

        actor = (command.actor or "system").strip() or "system"
        deadline = _parse_deadline(assignment.metadata.get_value(KEY_DEADLINE))
        late_allowed = parse_bool(assignment.metadata.get_value(KEY_LATE_ALLOWED))
        moment = _parse_moment(command.submitted_at) or dt.datetime.now(dt.UTC)
        is_late = deadline is not None and moment > deadline
        if is_late and not late_allowed:
            raise ValidationError(
                "The deadline has passed and late submission is not allowed "
                "for this assignment."
            )

        submission = submission_for(self._repository, str(assignment.id), str(student.id))
        created = submission is None
        if created:
            submission = UniversalObject.create(
                object_type=ObjectType.SUBMISSION,
                title=f"Submission: {student.title} → {assignment.title}",
                created_by=actor,
                status=ObjectStatus.ACTIVE,
                metadata=Metadata(),
            )
            submission.add_relationship(
                assignment.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
            )
            submission.add_relationship(
                student.id, RelationshipKind.AUTHORED_BY, Provenance.ASSERTED, actor=actor
            )

        def system_entry(key: str, value: str, layer: MetadataLayer) -> None:
            if submission.metadata.get_value(key) != value:
                submission.set_metadata(
                    MetadataEntry(key, value, layer, Provenance.SYSTEM), actor=actor
                )

        # --- file (replace idiom, same as the publication PDF) -----------
        if command.content is not None:
            old_key = submission.metadata.get_value(KEY_FILE_PATH)
            file_key = (
                f"teaching/submissions/{_sanitize(str(submission.id))}/"
                f"{_sanitize(command.file_name)}"
            )
            self._storage.save(file_key, command.content)
            if old_key and old_key != file_key:
                self._storage.delete(old_key)
            system_entry(KEY_FILE_NAME, command.file_name, MetadataLayer.L2_FILESYSTEM)
            system_entry(KEY_FILE_SIZE, str(len(command.content)), MetadataLayer.L2_FILESYSTEM)
            system_entry(
                KEY_FILE_MIME, command.mime_type or "", MetadataLayer.L2_FILESYSTEM
            )
            system_entry(KEY_FILE_PATH, file_key, MetadataLayer.L2_FILESYSTEM)

        # --- system facts (L1 timestamp, L5 computed lateness) -----------
        system_entry(
            KEY_SUBMITTED_AT, moment.isoformat(), MetadataLayer.L1_SYSTEM
        )
        system_entry(KEY_IS_LATE, "true" if is_late else "false", MetadataLayer.L5_INFERRED)
        if command.comments is not None and (
            submission.metadata.get_value(KEY_COMMENTS) != command.comments
        ):
            submission.set_metadata(
                MetadataEntry(
                    KEY_COMMENTS, command.comments,
                    MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED,
                ),
                actor=actor,
            )

        self._repository.save(submission)
        events = submission.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return SubmissionOutput.from_domain(submission, events, student=student)
