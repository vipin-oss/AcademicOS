"""Use case: Delete an action item."""
from __future__ import annotations

from app.application.commands.delete_action_item import DeleteActionItemCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteActionItemUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteActionItemCommand) -> None:
        obj = self._repository.get_by_id(command.action_id)
        if obj is None or obj.object_type is not ObjectType.TASK:
            raise ObjectNotFoundError(f"Action item {command.action_id} not found.")
        self._repository.delete(command.action_id)
