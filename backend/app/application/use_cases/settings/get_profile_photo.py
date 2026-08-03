"""Use case: Read the profile photo blob (404 when none is set)."""
from __future__ import annotations

from app.application.dtos.settings import (
    PHOTO_STORAGE_KEY,
    ProfilePhotoOutput,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_profile_photo import GetProfilePhotoQuery
from app.application.use_cases.settings.helpers import (
    get_or_create_settings,
    read_photo_meta,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetProfilePhotoUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, query: GetProfilePhotoQuery) -> ProfilePhotoOutput:
        del query
        obj = get_or_create_settings(self._repository)
        has_photo, mime_type, file_name = read_photo_meta(obj)
        if not has_photo:
            raise ObjectNotFoundError("No profile photo is set.")
        try:
            content = self._storage.read(PHOTO_STORAGE_KEY)
        except (OSError, ValueError) as exc:
            raise ObjectNotFoundError("Profile photo blob is missing from storage.") from exc
        return ProfilePhotoOutput(
            file_name=file_name or "profile-photo",
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(content),
            content=content,
        )
