"""Use case: Get (fetch) a Publication by id.

Mirrors ``GetDocumentUseCase``: non-publication Objects are reported as
not-found; linked Objects are batch-resolved in ONE ``find_by_ids`` call.
"""
from __future__ import annotations

from app.application.dtos.publication import (
    PublicationOutput,
    linked_target_ids,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_publication import GetPublicationQuery
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetPublicationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetPublicationQuery) -> PublicationOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.PUBLICATION:
            raise ObjectNotFoundError(f"Publication {query.object_id} not found.")
        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        # No events are emitted on a read; pass an empty list.
        return PublicationOutput.from_domain(obj, [], linked_by_id=linked_by_id)
