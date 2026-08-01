"""Use case: Get (fetch) a Document by id.

Mirrors ``GetObjectUseCase``. An id that exists but belongs to a non-document
Object is reported as not-found (the Documents slice exposes Documents only).
The linked Object's type/title are denormalised best-effort for the UI.
"""
from __future__ import annotations

from app.application.dtos.document import DocumentOutput, linked_object_id
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_document import GetDocumentQuery
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetDocumentUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetDocumentQuery) -> DocumentOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.DOCUMENT:
            raise ObjectNotFoundError(f"Document {query.object_id} not found.")
        link_id = linked_object_id(obj)
        linked = self._repository.get_by_id(link_id) if link_id is not None else None
        # No events are emitted on a read; pass an empty list.
        return DocumentOutput.from_domain(obj, [], linked=linked)
