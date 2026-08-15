"""Use case: List Publications (paginated, reference-manager filters).

Mirrors ``ListDocumentsUseCase``: pagination in the Application layer over
repository results (frozen interface), stable id ordering, ONE ``find_by_ids``
batch to denormalise links (no N+1). Adds the search/filter surface the
module promises: ``q`` (AND-matched tokens across title, authors, DOI,
journal, conference, keywords, publisher, ISBN, ISSN), plus exact filters on
``publication_type`` / ``year`` / ``quartile`` / ``pipeline_stage`` /
``status``, and ``object_id`` for relationship-scoped lenses
(future AI: "papers funded by Project X" = one query param).
"""
from __future__ import annotations

from app.application.dtos.publication import (
    ListPublicationsResult,
    PublicationOutput,
    linked_target_ids,
)
from app.application.queries.list_publications import ListPublicationsQuery
from app.application.validators.publication import (
    assert_valid_list_publications_query,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


def _searchable_text(out: PublicationOutput) -> str:
    return " ".join(
        [
            out.title,
            " ".join(a.get("name", "") for a in out.authors),
            out.doi or "",
            out.journal or "",
            out.conference or "",
            out.publisher or "",
            out.issn or "",
            out.isbn or "",
            " ".join(out.keywords),
            " ".join(out.tags),
        ]
    ).casefold()


def _matches(out: PublicationOutput, query: ListPublicationsQuery) -> bool:
    if query.publication_type and out.publication_type != query.publication_type:
        return False
    if query.year is not None and out.year != query.year:
        return False
    if query.quartile and out.quartile != query.quartile:
        return False
    if query.pipeline_stage and out.pipeline_stage != query.pipeline_stage:
        return False
    if query.status and out.status != query.status:
        return False
    if query.q:
        haystack = _searchable_text(out)
        tokens = [t for t in query.q.casefold().split() if t]
        if not all(token in haystack for token in tokens):
            return False
    return True


class ListPublicationsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListPublicationsQuery) -> ListPublicationsResult:
        assert_valid_list_publications_query(query)

        # M26 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find) instead of loading every PUBLICATION and hydrating all
        # JSONB metadata before slicing. The slow path below is preserved for
        # queries with criteria the SQL projection cannot express (q tokens,
        # year/quartile/pipeline filters, the relationship-scoped lens).
        plain = (
            not (query.q or "").strip()
            and query.object_id is None
            and query.publication_type is None
            and query.year is None
            and query.quartile is None
            and query.pipeline_stage is None
            and query.status is None
        )
        if plain:
            total_count = self._repository.count(object_type=ObjectType.PUBLICATION)
            page = self._repository.find(
                object_type=ObjectType.PUBLICATION,
                page=query.page,
                page_size=query.page_size,
                sort_by="id",
                order="asc",
            )
            all_ids: list[ObjectId] = []
            for pub in page:
                all_ids.extend(linked_target_ids(pub))
            linked_by_id = {
                str(o.id): o for o in self._repository.find_by_ids(all_ids)
            }
            items = [
                PublicationOutput.from_domain(pub, [], linked_by_id=linked_by_id)
                for pub in page
            ]
            return ListPublicationsResult(
                items=items,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        publications = self._repository.find_by_type(ObjectType.PUBLICATION)

        if query.object_id is not None:
            target = str(query.object_id)
            publications = [
                pub
                for pub in publications
                if target in {str(oid) for oid in linked_target_ids(pub)}
            ]

        outputs = [PublicationOutput.from_domain(pub, []) for pub in publications]
        outputs = [out for out in outputs if _matches(out, query)]

        total_count = len(outputs)

        # Default ordering: by id (stable, deterministic) — same as Objects.
        outputs.sort(key=lambda out: out.id)
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        # Batch-resolve linked objects for the page slice only.
        all_ids = []
        for out in page_items:
            raw = next(p for p in publications if str(p.id) == out.id)
            all_ids.extend(linked_target_ids(raw))
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        items = []
        for out in page_items:
            raw = next(p for p in publications if str(p.id) == out.id)
            items.append(PublicationOutput.from_domain(raw, [], linked_by_id=linked_by_id))

        return ListPublicationsResult(
            items=items,
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
