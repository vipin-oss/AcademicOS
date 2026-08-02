"""Use case: Remove one student from a Class roster (PART C).

Removes the ENROLLED_IN edge from the Student Object. Evidence already
produced (Submission Objects, attendance records) is intentionally kept —
removing a student from a roster must never rewrite history; the gradebook
simply stops showing them as a roster row.
"""
from __future__ import annotations

from app.application.commands.unenroll_student import UnenrollStudentCommand
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, Provenance, RelationshipKind


class UnenrollStudentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UnenrollStudentCommand) -> None:
        cls = self._repository.get_by_id(command.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.class_id} not found.")
        student = self._repository.get_by_id(command.student_id)
        if student is None or student.object_type is not ObjectType.STUDENT:
            raise ObjectNotFoundError(f"Student {command.student_id} not found.")

        actor = (command.actor or "system").strip() or "system"
        if str(cls.id) not in {
            str(oid) for oid in student.related_ids(RelationshipKind.ENROLLED_IN)
        }:
            raise ValidationError(
                f"Student {command.student_id} is not enrolled in class {command.class_id}."
            )
        student.remove_relationship(
            cls.id, RelationshipKind.ENROLLED_IN, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(student)
        events = student.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
