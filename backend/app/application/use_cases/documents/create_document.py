"""Use case: Upload a Document (file + metadata + optional Object link).

Vertical slice flow (mirrors ``CreateObjectUseCase``):
  Input DTO -> Validation -> store blob via the FileStorage port -> Domain
  Object creation (``object_type = document``) -> asserted ``belongs_to`` link
  -> Repository Interface -> Domain Events -> Output DTO

The blob is stored *before* the aggregate is persisted, so a write failure can
never leave a saved Document pointing at a missing file (at worst, one orphan
blob). Depends only on the ``ObjectRepository`` and ``FileStorage`` ports —
no SQLAlchemy, FastAPI, or filesystem imports here.
"""
from __future__ import annotations

import re

from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import (
    KEY_DESCRIPTION,
    KEY_DOCUMENT_TYPE,
    KEY_FILE_NAME,
    KEY_FILE_PATH,
    KEY_FILE_SIZE,
    KEY_MIME_TYPE,
    KEY_TAGS,
    DocumentOutput,
    encode_tags,
)
from app.application.exceptions import ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.ports.file_storage import FileStorage
from app.application.validators.document import assert_valid_create_document_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(part: str) -> str:
    """Make one storage-key segment safe on every filesystem."""
    return _SAFE_CHARS.sub("_", part).strip("._") or "unnamed"


def storage_key_for(object_id: ObjectId, file_name: str) -> str:
    """Storage key for a document blob: ``documents/<id>/<file-name>``."""
    return f"documents/{_sanitize(str(object_id))}/{_sanitize(file_name)}"


class CreateDocumentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._event_publisher = event_publisher

    def execute(self, command: CreateDocumentCommand) -> DocumentOutput:
        data = command.input

        # 1. Validate boundary input
        assert_valid_create_document_input(data)

        # 2. The linked Object must exist (Blueprint §4: belongs_to is asserted)
        if data.object_id is not None and not self._repository.exists(data.object_id):
            raise ValidationError(f"Linked object {data.object_id} not found.")

        # 3. Store the blob first (identity minted up-front, before persistence)
        document_id = ObjectId.generate(ObjectType.DOCUMENT)
        file_key = storage_key_for(document_id, data.file_name)
        self._storage.save(file_key, data.content)

        # 4. Assemble the seven-layer metadata record. File facts are system
        #    facts (L2); the upload form is human-asserted (L6, FR-MET-009 safe).
        entries = [
            MetadataEntry(
                KEY_DOCUMENT_TYPE,
                data.document_type,
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            ),
            MetadataEntry(KEY_FILE_NAME, data.file_name, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
            MetadataEntry(KEY_FILE_SIZE, str(data.file_size), MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
            MetadataEntry(KEY_MIME_TYPE, data.mime_type, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
            MetadataEntry(KEY_FILE_PATH, file_key, MetadataLayer.L2_FILESYSTEM, Provenance.SYSTEM),
        ]
        if data.description:
            entries.append(
                MetadataEntry(
                    KEY_DESCRIPTION,
                    data.description,
                    MetadataLayer.L6_HUMAN_ASSERTED,
                    Provenance.ASSERTED,
                )
            )
        if data.tags:
            entries.append(
                MetadataEntry(
                    KEY_TAGS,
                    encode_tags(data.tags),
                    MetadataLayer.L6_HUMAN_ASSERTED,
                    Provenance.ASSERTED,
                )
            )

        # 5. Create the domain aggregate (emits ObjectCreated)
        obj = UniversalObject.create(
            object_type=ObjectType.DOCUMENT,
            title=data.title.strip(),
            created_by=data.uploaded_by.strip(),
            object_id=document_id,
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )

        # 6. Structural link (asserted belongs_to edge, Blueprint §4)
        if data.object_id is not None:
            obj.add_relationship(
                data.object_id,
                RelationshipKind.BELONGS_TO,
                Provenance.ASSERTED,
                actor=data.uploaded_by,
            )

        # 7. Persist via the abstract repository interface
        self._repository.save(obj)

        # 8. Collect + project domain events
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        # 9. Output DTO (the linked Object was validated in step 2)
        linked = self._repository.get_by_id(data.object_id) if data.object_id else None
        return DocumentOutput.from_domain(obj, events, linked=linked)
