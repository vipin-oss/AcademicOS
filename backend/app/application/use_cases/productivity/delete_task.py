"""Use case: Delete a personal Productivity task (plain delete, 404)."""
from __future__ import annotations

from app.application.commands.delete_task import DeleteTaskCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.application.use_cases.productivity.helpers import is_personal_task
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteTaskUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteTaskCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.TASK or not is_personal_task(obj):
            raise ObjectNotFoundError(f"Personal task {command.object_id} not found.")
        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
