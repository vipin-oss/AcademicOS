"""Use case: Delete an Event.

Mirrors ``DeleteProposalUseCase`` (plain delete, 404): the event's section
rows ride as its own metadata so nothing cascades; linked faculty, students,
projects, grants, committees, publications and documents are institutional
records on OTHER Objects and survive by design (the frozen dangling-edge
tolerance).
"""
from __future__ import annotations

from app.application.commands.delete_event import DeleteEventCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteEventUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteEventCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.EVENT:
            raise ObjectNotFoundError(f"Event {command.object_id} not found.")
        self._repository.delete(command.object_id)
