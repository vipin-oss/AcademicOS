"""Use case: Delete a Document (aggregate + stored blob).

Per the frozen repository behaviour, deletion is a hard delete (``delete``
removes the row) — the same semantics as the Objects slice. The stored blob is
removed best-effort through the ``FileStorage`` port: a missing file never
blocks the delete.
"""
from __future__ import annotations

from app.application.commands.delete_document import DeleteDocumentCommand
from app.application.dtos.document import KEY_FILE_PATH
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteDocumentUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeleteDocumentCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.DOCUMENT:
            raise ObjectNotFoundError(f"Document {command.object_id} not found.")

        file_key = obj.metadata.get_value(KEY_FILE_PATH)
        if file_key:
            self._storage.delete(file_key)
        self._repository.delete(command.object_id)
