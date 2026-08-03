"""Use case: Delete a personal calendar entry (plain delete, 404)."""
from __future__ import annotations

from app.application.commands.delete_calendar_entry import DeleteCalendarEntryCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteCalendarEntryUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteCalendarEntryCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.CALENDAR_ENTRY:
            raise ObjectNotFoundError(f"Calendar entry {command.object_id} not found.")
        self._repository.delete(command.object_id)
