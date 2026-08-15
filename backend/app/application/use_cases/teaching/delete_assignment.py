"""Use case: Delete an Assignment (cascade: submissions + blobs).

Mirrors ``DeletePublicationUseCase`` (hard delete, best-effort blob
removal); the cascade deletes and REPORTS every Submission Object of the
assignment (with uploaded files) plus the assignment attachment blob.
"""
from __future__ import annotations

from app.application.commands.delete_assignment import DeleteAssignmentCommand
from app.application.dtos.teaching import KEY_ATTACHMENT_PATH, KEY_FILE_PATH
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.application.use_cases.teaching.helpers import submissions_of_assignment
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteAssignmentUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeleteAssignmentCommand) -> dict:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {command.object_id} not found.")

        deleted = {"assignment_id": str(obj.id), "submissions": 0}
        for submission in submissions_of_assignment(self._repository, str(obj.id)):
            file_key = submission.metadata.get_value(KEY_FILE_PATH)
            if file_key:
                self._storage.delete(file_key)
            self._repository.delete(submission.id)
            deleted["submissions"] += 1

        attachment_key = obj.metadata.get_value(KEY_ATTACHMENT_PATH)
        if attachment_key:
            self._storage.delete(attachment_key)
        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
        return deleted
