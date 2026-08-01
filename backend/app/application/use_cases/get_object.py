"""Use case: Get (fetch) a Universal Object by id."""
from __future__ import annotations

from app.application.dtos.object import CreateObjectOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_object import GetObjectQuery
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository


class GetObjectUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetObjectQuery) -> CreateObjectOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object {query.object_id} not found.")
        # No events are emitted on a read; pass an empty list.
        return CreateObjectOutput.from_domain(obj, [])
