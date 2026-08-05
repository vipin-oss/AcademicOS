"""Use case: Get the raw extracted text of one intake item (M2).

Read-only. The item must belong to the session, its extraction must have run
successfully (``ExtractionStatus.EXTRACTED`` with a text blob), and the blob
must still exist — every gap answers 404, never a fabricated empty document.
"""
from __future__ import annotations

from app.application.dtos.extraction import ExtractionStatus
from app.application.dtos.intake import KEY_EXTRACTION, KEY_SESSION_ID, json_decode
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_intake_extracted_text import GetIntakeExtractedTextQuery
from app.application.use_cases.intake.helpers import get_intake_session_or_404
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


class GetIntakeExtractedTextUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, query: GetIntakeExtractedTextQuery) -> str:
        session = get_intake_session_or_404(self._repository, query.session_id)

        item = self._repository.get_by_id(ObjectId(query.item_id))
        if (
            item is None
            or item.object_type is not ObjectType.INTAKE_ITEM
            or (item.metadata.get_value(KEY_SESSION_ID) or "") != str(session.id)
        ):
            raise ObjectNotFoundError(f"Intake item {query.item_id} not found in this session.")

        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        text_key = descriptor.get("text_key") if isinstance(descriptor, dict) else None
        if (
            not isinstance(descriptor, dict)
            or descriptor.get("status") != ExtractionStatus.EXTRACTED.value
            or not text_key
        ):
            raise ObjectNotFoundError(
                "No extracted text exists for this item "
                "(unsupported format or not extracted yet)."
            )

        if not self._storage.exists(text_key):
            raise ObjectNotFoundError("The extracted text blob is missing from storage.")
        return self._storage.read(text_key).decode("utf-8")
