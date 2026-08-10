"""Use case: List Documents (paginated, optional linked-object filter).

Mirrors ``ListObjectsUseCase``: pagination is performed in the Application
layer over repository results, preserving the frozen repository interface.
Default ordering is by ``id`` for deterministic, stable results. Linked
objects' titles/types are resolved in ONE ``find_by_ids`` batch (no N+1).
"""
from __future__ import annotations

from app.application.dtos.document import (
    DocumentOutput,
    ListDocumentsResult,
    linked_object_id,
)
from app.application.queries.list_documents import ListDocumentsQuery
from app.application.validators.document import assert_valid_list_documents_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListDocumentsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListDocumentsQuery) -> ListDocumentsResult:
        assert_valid_list_documents_query(query)

        # M26 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find) instead of loading every DOCUMENT and hydrating all
        # JSONB metadata before slicing. The slow path below is preserved
        # verbatim for queries that carry criteria the SQL projection cannot
        # express (the linked-object lens).
        if query.object_id is None:
            total_count = self._repository.count(object_type=ObjectType.DOCUMENT)
            page = self._repository.find(
                object_type=ObjectType.DOCUMENT,
                page=query.page,
                page_size=query.page_size,
                sort_by="id",
                order="asc",
            )
            link_ids = [
                link for doc in page if (link := linked_object_id(doc)) is not None
            ]
            linked_by_id = {
                str(obj.id): obj for obj in self._repository.find_by_ids(link_ids)
            }
            return ListDocumentsResult(
                items=[
                    DocumentOutput.from_domain(
                        doc,
                        [],
                        linked=linked_by_id.get(str(linked_object_id(doc)))
                        if linked_object_id(doc) is not None
                        else None,
                    )
                    for doc in page
                ],
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        documents = self._repository.find_by_type(ObjectType.DOCUMENT)

        if query.object_id is not None:
            target = str(query.object_id)
            documents = [
                doc for doc in documents
                if linked_object_id(doc) is not None and str(linked_object_id(doc)) == target
            ]

        total_count = len(documents)

        # Default ordering: by id (stable, deterministic) — same as Objects.
        ordered = sorted(documents, key=lambda o: str(o.id))
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        page_items = ordered[start:end]

        # Batch-resolve linked objects for denormalised titles/types.
        link_ids = [
            link for doc in page_items if (link := linked_object_id(doc)) is not None
        ]
        linked_by_id = {
            str(obj.id): obj for obj in self._repository.find_by_ids(link_ids)
        }

        return ListDocumentsResult(
            items=[
                DocumentOutput.from_domain(
                    doc,
                    [],
                    linked=linked_by_id.get(str(linked_object_id(doc)))
                    if linked_object_id(doc) is not None
                    else None,
                )
                for doc in page_items
            ],
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
