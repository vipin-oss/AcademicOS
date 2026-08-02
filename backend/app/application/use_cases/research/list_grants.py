"""Use case: List Grants (paginated; q + project/agency lenses, status).

Mirrors ``ListStudentsUseCase``: portable filters, deterministic registry
ordering (grant number, then title), ONE find_by_ids batch on the page slice.
Each row carries its computed budget so the list renders amounts without
extra round-trips at registry scale.
"""
from __future__ import annotations

from app.application.dtos.research import (
    GrantOutput,
    ListGrantsResult,
    linked_target_ids,
)
from app.application.queries.list_grants import ListGrantsQuery
from app.application.use_cases.research.helpers import grant_totals
from app.application.validators.research import assert_valid_list_grants_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _searchable_text(out: GrantOutput) -> str:
    return " ".join(
        [
            out.title,
            out.grant_number or "",
            out.release_schedule or "",
            out.notes or "",
        ]
    ).casefold()


class ListGrantsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListGrantsQuery) -> ListGrantsResult:
        assert_valid_list_grants_query(query)

        grants = self._repository.find_by_type(ObjectType.GRANT)

        if query.project_id is not None:
            target = str(query.project_id)
            grants = [
                g
                for g in grants
                if target in {str(oid) for oid in linked_target_ids(g, RelationshipKind.FUNDS)}
            ]
        if query.agency_id is not None:
            target = str(query.agency_id)
            grants = [
                g
                for g in grants
                if target
                in {str(oid) for oid in linked_target_ids(g, RelationshipKind.FUNDED_BY)}
            ]

        outputs = [GrantOutput.from_domain(g, []) for g in grants]
        outputs = [
            out for out in outputs
            if (not query.status or out.status == query.status)
            and (
                not query.q or not query.q.strip()
                or all(
                    token in _searchable_text(out)
                    for token in query.q.casefold().split() if token
                )
            )
        ]
        total_count = len(outputs)
        outputs.sort(key=lambda out: (out.grant_number or "￿", out.title.casefold(), out.id))
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        by_id = {str(g.id): g for g in grants}
        all_ids: list = []
        for out in page_items:
            all_ids.extend(linked_target_ids(by_id[out.id]))
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}

        items = []
        for out in page_items:
            obj = by_id[out.id]
            enriched = GrantOutput.from_domain(obj, [], linked_by_id=linked_by_id)
            enriched.budget = grant_totals(self._repository, obj)
            items.append(enriched)

        return ListGrantsResult(
            items=items, total_count=total_count, page=query.page, page_size=query.page_size
        )
