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
