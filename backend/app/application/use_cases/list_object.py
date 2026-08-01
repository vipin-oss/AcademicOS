"""Use case: List Universal Objects (paginated).

Pagination is performed in the Application layer over the repository ``list()``
result, preserving the frozen repository interface (no new repository method).
Default ordering is by ``id`` for deterministic, stable results.
"""
from __future__ import annotations

from app.application.dtos.object import CreateObjectOutput, ListObjectsResult
from app.application.exceptions import ValidationError
from app.application.queries.list_objects import ListObjectsQuery
from app.application.validators.object import assert_valid_list_query
from app.domain.repositories.object_repository import ObjectRepository


class ListObjectsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListObjectsQuery) -> ListObjectsResult:
        assert_valid_list_query(query)

        all_objs = self._repository.list()
        total_count = len(all_objs)

        # Default ordering: by id (stable, deterministic).
        ordered = sorted(all_objs, key=lambda o: str(o.id))
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        page_items = ordered[start:end]

        return ListObjectsResult(
            items=[CreateObjectOutput.from_domain(o, []) for o in page_items],
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
