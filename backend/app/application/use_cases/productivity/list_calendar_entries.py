"""Use case: List personal calendar entries (window + token search)."""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_CATEGORY,
    KEY_END_DATE,
    KEY_START_DATE,
    ListCalendarEntriesResult,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_calendar_entries import ListCalendarEntriesQuery
from app.application.use_cases.productivity.helpers import (
    _meta,
    entry_output,
    token_match,
)
from app.application.validators.productivity import assert_search_window
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListCalendarEntriesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListCalendarEntriesQuery) -> ListCalendarEntriesResult:
        assert_search_window(query.date_from, query.date_to)
        if query.page < 1 or query.page_size < 1 or query.page_size > 100:
            raise ValidationError("Invalid pagination (page >= 1, 1 <= page_size <= 100).")
        rows = self._repository.find_by_type(ObjectType.CALENDAR_ENTRY)

        def keep(obj) -> bool:
            meta = _meta(obj)
            if query.category and (meta.get(KEY_CATEGORY) or "") != query.category.strip().lower():
                return False
            start = meta.get(KEY_START_DATE) or ""
            end = meta.get(KEY_END_DATE) or start
            if query.date_from and end < query.date_from:
                return False
            if query.date_to and start > query.date_to:
                return False
            haystack = " ".join(
                [obj.title, meta.get("description") or "", meta.get("location") or "", meta.get("tags") or ""]
            )
            return token_match(haystack, query.q)

        rows = [obj for obj in rows if keep(obj)]
        rows.sort(
            key=lambda obj: (
                _meta(obj).get(KEY_START_DATE) or "",
                _meta(obj).get("start_time") or "",
                obj.title.casefold(),
                str(obj.id),
            )
        )
        total = len(rows)
        start = (query.page - 1) * query.page_size
        page_items = [entry_output(obj) for obj in rows[start : start + query.page_size]]
        return ListCalendarEntriesResult(items=page_items, total_count=total, page=query.page, page_size=query.page_size)
