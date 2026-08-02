"""Use case: Attach (or replace) an Assignment's reference file (PART D).

Mirrors ``AttachPublicationPdfUseCase`` one-to-one: the blob goes through
the ``FileStorage`` port under ``teaching/assignments/{id}/``; file facts
are L2 system metadata, so replacing simply overwrites the same keys and
the old blob is removed.
"""
from __future__ import annotations

import re

from app.application.commands.attach_assignment_file import AttachAssignmentFileCommand
from app.application.dtos.teaching import (
    KEY_ATTACHMENT_MIME,
    KEY_ATTACHMENT_NAME,
    KEY_ATTACHMENT_PATH,
    KEY_ATTACHMENT_SIZE,
    AssignmentOutput,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.teaching.helpers import class_id_of_assignment
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(part: str) -> str:
    return _SAFE_CHARS.sub("_", part).strip("._") or "unnamed"


class AttachAssignmentFileUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: AttachAssignmentFileCommand) -> AssignmentOutput:
        if not command.content:
            raise ValidationError("The uploaded file is empty.")

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {command.object_id} not found.")

        actor = command.actor or "system"
        old_key = obj.metadata.get_value(KEY_ATTACHMENT_PATH)

        file_key = f"teaching/assignments/{_sanitize(str(obj.id))}/{_sanitize(command.file_name)}"
        self._storage.save(file_key, command.content)
        if old_key and old_key != file_key:
            self._storage.delete(old_key)

        for key, value in (
            (KEY_ATTACHMENT_NAME, command.file_name),
            (KEY_ATTACHMENT_SIZE, str(len(command.content))),
            (KEY_ATTACHMENT_MIME, command.mime_type),
            (KEY_ATTACHMENT_PATH, file_key),
        ):
            if obj.metadata.get_value(key) != value:
                obj.set_metadata(
                    MetadataEntry(key, value, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
                    actor=actor,
                )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        class_id = class_id_of_assignment(obj)
        class_obj = (
            self._repository.get_by_id(ObjectId(class_id)) if class_id is not None else None
        )
        return AssignmentOutput.from_domain(obj, events, class_obj=class_obj)
