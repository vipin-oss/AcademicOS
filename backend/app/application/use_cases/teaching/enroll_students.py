"""Use case: Enroll students into a Class (manual / id list — PART C).

Writes the ENROLLED_IN edge ON each Student Object (single write path for
enrollment), so rosters, student lenses and dashboards all read the same
edge. Idempotent per student: already-enrolled ids are reported, never
duplicated; unknown ids become per-row errors, never 500s.
"""
from __future__ import annotations

from app.application.commands.enroll_students import EnrollStudentsCommand
from app.application.dtos.teaching import EnrollmentResult
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.teaching.helpers import enrolled_students
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, Provenance, RelationshipKind


class EnrollStudentsUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: EnrollStudentsCommand) -> EnrollmentResult:
        if not command.student_ids:
            raise ValidationError("Provide at least one student id to enroll.")
        cls = self._repository.get_by_id(command.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.class_id} not found.")

        actor = (command.actor or "system").strip() or "system"
        already = {str(s.id) for s in enrolled_students(self._repository, str(cls.id))}
        result = EnrollmentResult()
        seen: set[str] = set()

        for student_id in command.student_ids:
            sid = str(student_id)
            if sid in seen:
                continue
            seen.add(sid)
            student = self._repository.get_by_id(student_id)
            if student is None or student.object_type is not ObjectType.STUDENT:
                result.errors.append(
                    {"student_id": sid, "message": "Student not found; skipped."}
                )
                continue
            if sid in already:
                result.already_enrolled.append(sid)
                continue
            student.add_relationship(
                cls.id, RelationshipKind.ENROLLED_IN, Provenance.ASSERTED, actor=actor
            )
            self._repository.save(student)
            events = student.pop_domain_events()
            if self._event_publisher is not None:
                self._event_publisher.publish(events)
            result.enrolled.append(sid)
        return result
