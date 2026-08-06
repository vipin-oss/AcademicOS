"""Use case: commit one intake item into a Document (Sprint-3 M1).

The Commit Engine's single logical unit. Eligibility + idempotency live
here; the actual Document creation is delegated to the existing
``CreateDocumentUseCase`` (never duplicated). The item is then marked
``COMMITTED`` with a pointer to the created Document, so a retry is a
409 carrying the existing document id — never a duplicate write.

Eligibility contract (documented):
- the item exists, is an INTAKE_ITEM and is ``AWAITING_REVIEW``;
- its session is ``COMPLETED``;
- it was staged (content hash + staged blob present);
- its extraction descriptor is ``extracted``.

The Document is created with ``object_id = item id``, so the existing
use case adds the ``BELONGS_TO`` edge (document -> item) with its own
existence validation — the item↔document link is one direction, and
``find_inbound`` on the item yields the document. No new edge code here.
"""
from __future__ import annotations

from app.application.commands.commit_intake_item import CommitIntakeItemCommand
from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import CreateDocumentInput
from app.application.dtos.intake import (
    KEY_COMMITTED_DOCUMENT,
    KEY_EXTENSION,
    KEY_INTAKE_STATUS,
    KEY_MIME_TYPE,
    KEY_SESSION_ID,
    KEY_SHA256,
    KEY_SIZE_BYTES,
    KEY_STAGED_KEY,
    CommitItemOutput,
    IntakeItemStatus,
    IntakeSessionStatus,
    _extraction_dict_of,
    intake_session_status_of,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.validators.document import DOCUMENT_TYPES
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

_FALLBACK_MIME = "application/octet-stream"


def _system_entry(key: str, value: str) -> MetadataEntry:
    """Intake item state is a system fact (L1 / SYSTEM), like the runner's."""
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


class CommitItemUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        document_creator: CreateDocumentUseCase,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._document_creator = document_creator

    def execute(self, command: CommitIntakeItemCommand) -> CommitItemOutput:
        item = self._repository.get_by_id(ObjectId(command.item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {command.item_id}")

        # --- idempotency: committed items are terminal ---------------------
        status = item.metadata.get_value(KEY_INTAKE_STATUS)
        if status == IntakeItemStatus.COMMITTED.value:
            document_id = item.metadata.get_value(KEY_COMMITTED_DOCUMENT) or "unknown"
            raise ObjectAlreadyExistsError(
                f"Item {command.item_id} is already committed as document {document_id}."
            )

        # --- eligibility ----------------------------------------------------
        if status != IntakeItemStatus.AWAITING_REVIEW.value:
            raise ValidationError(f"Cannot commit item in status {status!r}.")
        if not item.metadata.get_value(KEY_SHA256):
            raise ValidationError("Item has no content hash; it was not staged.")
        descriptor = _extraction_dict_of(item)
        if descriptor is None or descriptor.get("status") != "extracted":
            raise ValidationError(
                "Item has no extracted text; only extracted items can be committed."
            )

        session_id = item.metadata.get_value(KEY_SESSION_ID)
        if not session_id:
            raise ValidationError("Item has no intake session.")
        session = self._repository.get_by_id(ObjectId(session_id))
        if session is None:
            raise ValidationError(f"Intake session {session_id} not found.")
        if intake_session_status_of(session) is not IntakeSessionStatus.COMPLETED:
            raise ValidationError("Session must be completed before committing items.")

        # --- staged blob -----------------------------------------------------
        staged_key = item.metadata.get_value(KEY_STAGED_KEY)
        if not staged_key:
            raise ValidationError("Item has no staged blob.")
        try:
            content = self._storage.read(staged_key)
        except FileNotFoundError:
            raise ValidationError(
                f"Staged blob {staged_key!r} is missing; re-run the session."
            ) from None

        if command.dry_run:
            # Preview: eligibility already passed; report what a real commit
            # would create without creating or mutating anything.
            return CommitItemOutput(
                item_id=str(item.id),
                document_id="",
                document_title="",
            )

        # --- reuse CreateDocumentUseCase (the sanctioned document path) -----
        extension = item.metadata.get_value(KEY_EXTENSION) or ""
        document_type = extension if extension in DOCUMENT_TYPES else "unknown"
        file_size = int(item.metadata.get_value(KEY_SIZE_BYTES) or 0)
        document = self._document_creator.execute(
            CreateDocumentCommand(
                input=CreateDocumentInput(
                    title=item.title,
                    document_type=document_type,
                    uploaded_by=command.actor,
                    file_name=item.title,
                    file_size=file_size,
                    mime_type=item.metadata.get_value(KEY_MIME_TYPE) or _FALLBACK_MIME,
                    content=content,
                    status=ObjectStatus.ACTIVE,
                    # The BELONGS_TO edge (document -> item) is added by the
                    # existing use case with its own existence validation.
                    object_id=item.id,
                )
            )
        )

        # --- mark committed (idempotent terminal state) ---------------------
        item.set_metadata(_system_entry(KEY_COMMITTED_DOCUMENT, str(document.id)), actor=command.actor)
        item.set_metadata(_system_entry(KEY_INTAKE_STATUS, IntakeItemStatus.COMMITTED.value), actor=command.actor)
        self._repository.save(item)

        return CommitItemOutput(
            item_id=str(item.id),
            document_id=str(document.id),
            document_title=document.title,
        )
