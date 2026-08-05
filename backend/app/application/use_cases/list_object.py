"""Use case: List Universal Objects (paginated).

Pagination is delegated to the repository read projections (R2): ``count()``
answers ``total_count`` and ``find()`` returns the requested page — SQL
``LIMIT/OFFSET`` instead of loading every Object into memory. Default
ordering is by ``id`` ascending (deterministic, stable), preserving the
pre-R2 behaviour.
"""
from __future__ import annotations

from app.application.dtos.object import CreateObjectOutput, ListObjectsResult
from app.application.queries.list_objects import ListObjectsQuery
from app.application.validators.object import assert_valid_list_query
from app.domain.repositories.object_repository import ObjectRepository


class ListObjectsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListObjectsQuery) -> ListObjectsResult:
        assert_valid_list_query(query)

        total_count = self._repository.count(
            object_type=query.object_type,
            status=query.status,
        )
        page_items = self._repository.find(
            object_type=query.object_type,
            status=query.status,
            page=query.page,
            page_size=query.page_size,
            sort_by="id",
            order="asc",
        )

        return ListObjectsResult(
            items=[CreateObjectOutput.from_domain(o, []) for o in page_items],
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
