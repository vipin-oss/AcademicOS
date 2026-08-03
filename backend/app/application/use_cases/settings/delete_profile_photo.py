"""Use case: Remove the profile photo (metadata markers + blob)."""
from __future__ import annotations

from app.application.commands.delete_profile_photo import DeleteProfilePhotoCommand
from app.application.dtos.settings import PHOTO_STORAGE_KEY
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.settings.helpers import (
    clear_photo_meta,
    get_or_create_settings,
)
from app.domain.repositories.object_repository import ObjectRepository


class DeleteProfilePhotoUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeleteProfilePhotoCommand) -> None:
        del command
        obj = get_or_create_settings(self._repository)
        self._storage.delete(PHOTO_STORAGE_KEY)  # missing keys are ignored
        clear_photo_meta(obj)
        self._repository.save(obj)
        obj.pop_domain_events()
