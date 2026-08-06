"""Use case: Delete a notification (plain delete, 404)."""
from __future__ import annotations

from app.application.commands.delete_notification import DeleteNotificationCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteNotificationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteNotificationCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.NOTIFICATION:
            raise ObjectNotFoundError(f"Notification {command.object_id} not found.")
        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
