"""Use case: List Funding Agencies (paginated, free-text search).

Mirrors ``ListStudentsUseCase``: token-AND search over name/scheme/contact/
email, deterministic name ordering (registry reading order).
"""
from __future__ import annotations

from app.application.dtos.research import AgencyOutput, ListAgenciesResult
from app.application.queries.list_agencies import ListAgenciesQuery
from app.application.validators.research import assert_valid_list_agencies_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _searchable_text(out: AgencyOutput) -> str:
    return " ".join(
        [
            out.name,
            out.scheme or "",
            out.contact_person or "",
            out.contact_email or "",
            out.address or "",
        ]
    ).casefold()


class ListAgenciesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListAgenciesQuery) -> ListAgenciesResult:
        assert_valid_list_agencies_query(query)

        # M27 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find, title_ci — the registry's name order, since
        # AgencyOutput.name is the object title) instead of loading every
        # FUNDING_AGENCY row and hydrating all JSONB metadata before slicing.
        # The slow path below is preserved for q/status filters.
        plain = not (query.q or "").strip() and query.status is None
        if plain:
            total_count = self._repository.count(object_type=ObjectType.FUNDING_AGENCY)
            page = self._repository.find(
                object_type=ObjectType.FUNDING_AGENCY,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            return ListAgenciesResult(
                items=[AgencyOutput.from_domain(a, []) for a in page],
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        agencies = self._repository.find_by_type(ObjectType.FUNDING_AGENCY)
        outputs = [AgencyOutput.from_domain(a, []) for a in agencies]
        outputs = [
            out
            for out in outputs
            if (not query.status or out.status == query.status)
            and (
                not query.q or not query.q.strip()
                or all(token in _searchable_text(out) for token in query.q.casefold().split() if token)
            )
        ]
        total_count = len(outputs)
        outputs.sort(key=lambda out: (out.name.casefold(), out.id))
        start = (query.page - 1) * query.page_size
        return ListAgenciesResult(
            items=outputs[start:start + query.page_size],
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
        )
