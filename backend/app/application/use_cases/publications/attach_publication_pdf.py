"""Use case: Attach (or replace) the primary PDF of a Publication.

Mirrors the documents slice's storage orchestration: the blob goes through the
``FileStorage`` port; file facts are recorded as L2 system metadata (the
seven-layer record), so a replacement PDF simply overwrites the same keys.
Re-attaching first deletes the previous blob under its recorded key.
"""
from __future__ import annotations

import re

from app.application.commands.attach_publication_pdf import (
    AttachPublicationPdfCommand,
)
from app.application.dtos.publication import (
    KEY_PDF_FILE_NAME,
    KEY_PDF_FILE_PATH,
    KEY_PDF_FILE_SIZE,
    KEY_PDF_MIME_TYPE,
    PublicationOutput,
    linked_target_ids,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(part: str) -> str:
    return _SAFE_CHARS.sub("_", part).strip("._") or "unnamed"


class AttachPublicationPdfUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: AttachPublicationPdfCommand) -> PublicationOutput:
        if not command.content:
            raise ValidationError("The uploaded file is empty.")

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.PUBLICATION:
            raise ObjectNotFoundError(f"Publication {command.object_id} not found.")

        actor = command.actor or "system"
        old_key = obj.metadata.get_value(KEY_PDF_FILE_PATH)

        file_key = f"publications/{_sanitize(str(obj.id))}/{_sanitize(command.file_name)}"
        self._storage.save(file_key, command.content)
        if old_key and old_key != file_key:
            self._storage.delete(old_key)

        for key, value in (
            (KEY_PDF_FILE_NAME, command.file_name),
            (KEY_PDF_FILE_SIZE, str(len(command.content))),
            (KEY_PDF_MIME_TYPE, command.mime_type),
            (KEY_PDF_FILE_PATH, file_key),
        ):
            if obj.metadata.get_value(key) != value:
                obj.set_metadata(
                    MetadataEntry(key, value, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
                    actor=actor,
                )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        return PublicationOutput.from_domain(obj, events, linked_by_id=linked_by_id)
