"""Use case: List the items of one session (paginated, path-ordered)."""
from __future__ import annotations

from app.application.dtos.intake import ListIntakeItemsResult, intake_item_output
from app.application.queries.list_intake_items import ListIntakeItemsQuery
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
)
from app.domain.repositories.object_repository import ObjectRepository


class ListIntakeItemsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListIntakeItemsQuery) -> ListIntakeItemsResult:
        obj = get_intake_session_or_404(self._repository, query.session_id)
        items = items_of_session(self._repository, str(obj.id))
        total = len(items)
        start = (query.page - 1) * query.page_size
        window = items[start : start + query.page_size]
        return ListIntakeItemsResult(
            items=[intake_item_output(i) for i in window],
            total_count=total,
            page=query.page,
            page_size=query.page_size,
        )
