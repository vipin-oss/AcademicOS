"""Use case: Delete a Universal Object.

Per the frozen repository behaviour, deletion is a hard delete (``delete`` removes
the row). No new delete strategy, no soft-delete columns — exactly the existing
domain/repository behaviour is used.
"""
from __future__ import annotations

from app.application.commands.delete_object import DeleteObjectCommand
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.domain.repositories.object_repository import ObjectRepository


class DeleteObjectUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteObjectCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object {command.object_id} not found.")
        # Graph integrity (S2 M3): never orphan inbound edges with a hard
        # delete. Reject when other objects still reference this one.
        try:
            assert_no_inbound_edges(self._repository, command.object_id)
        except ValidationError:
            raise
        self._repository.delete(command.object_id)
