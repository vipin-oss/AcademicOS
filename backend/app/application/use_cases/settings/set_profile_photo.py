"""Use case: Set the profile photo (PART 1) via the FileStorage port.

The blob lives under the fixed ``PHOTO_STORAGE_KEY`` (single user profile);
the settings object keeps only has/mime/name markers. Replaces any existing
photo — the storage adapter overwrites by contract.
"""
from __future__ import annotations

from app.application.commands.set_profile_photo import SetProfilePhotoCommand
from app.application.dtos.settings import (
    PHOTO_STORAGE_KEY,
    ProfilePhotoOutput,
)
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.settings.helpers import (
    get_or_create_settings,
    write_photo_meta,
)
from app.application.validators.settings import assert_valid_photo_input
from app.domain.repositories.object_repository import ObjectRepository


class SetProfilePhotoUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: SetProfilePhotoCommand) -> ProfilePhotoOutput:
        data = command.input
        assert_valid_photo_input(data)
        obj = get_or_create_settings(self._repository)
        self._storage.save(PHOTO_STORAGE_KEY, data.content)
        write_photo_meta(obj, data.mime_type, data.file_name.strip())
        self._repository.save(obj)
        obj.pop_domain_events()
        return ProfilePhotoOutput(
            file_name=data.file_name.strip(),
            mime_type=data.mime_type,
            size_bytes=len(data.content),
        )
