"""Use case: Delete a Submission (aggregate + uploaded file blob).

Faculty-side correction path (a mistaken upload/test record). Mirrors
``DeletePublicationUseCase``: hard delete via the frozen repository, blob
removal best-effort through the ``FileStorage`` port.
"""
from __future__ import annotations

from app.application.commands.delete_submission import DeleteSubmissionCommand
from app.application.dtos.teaching import KEY_FILE_PATH
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteSubmissionUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeleteSubmissionCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.SUBMISSION:
            raise ObjectNotFoundError(f"Submission {command.object_id} not found.")

        file_key = obj.metadata.get_value(KEY_FILE_PATH)
        if file_key:
            self._storage.delete(file_key)
        self._repository.delete(command.object_id)
