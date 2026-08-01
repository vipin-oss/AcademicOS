"""Use case: Delete a Publication (aggregate + attached PDF blob).

Per the frozen repository behaviour, deletion is a hard delete — the same
semantics as Objects and Documents. The attached PDF is removed best-effort
through the ``FileStorage`` port; a missing file never blocks the delete.
Linked Objects and linked Documents are untouched (edges die with the node).
"""
from __future__ import annotations

from app.application.commands.delete_publication import DeletePublicationCommand
from app.application.dtos.publication import KEY_PDF_FILE_PATH
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeletePublicationUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeletePublicationCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.PUBLICATION:
            raise ObjectNotFoundError(f"Publication {command.object_id} not found.")

        file_key = obj.metadata.get_value(KEY_PDF_FILE_PATH)
        if file_key:
            self._storage.delete(file_key)
        self._repository.delete(command.object_id)
