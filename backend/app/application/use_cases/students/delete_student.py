"""Use case: Delete a Student.

Mirrors ``DeletePublicationUseCase``. The student's Submission and
Attendance evidence lives on OTHER Objects (submission/attendance_session),
so evidence survives a roster cleanup by design — deleting the student only
removes the student Object itself. Relationship edges on other Objects that
point at the student (e.g. an enrollment edge does NOT — enrollment lives on
the student) become dangling only where the other modules already tolerate
missing targets (they skip unresolved ids on denormalisation).
"""
from __future__ import annotations

from app.application.commands.delete_student import DeleteStudentCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteStudentUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteStudentCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.STUDENT:
            raise ObjectNotFoundError(f"Student {command.object_id} not found.")
        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
