"""Use case: List personal tasks (PART 3 filters + PART 7 token search).

Pinned-first, then nearest due date, then title (a stable personal order);
completed rows sink below open ones at the same priority so the default
list answers "what needs attention" first.
"""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_CATEGORY,
    KEY_DUE_DATE,
    KEY_PRIORITY,
    ListTasksResult,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_tasks import ListTasksQuery
from app.application.use_cases.productivity.helpers import (
    KEY_PINNED,
    _meta,
    is_true,
    personal_tasks,
    task_is_done,
    task_is_overdue,
    task_output,
    today_iso,
    token_match,
)
from app.application.validators.productivity import assert_search_window
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListTasksUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListTasksQuery) -> ListTasksResult:
        assert_search_window(query.due_from, query.due_to)
        if query.page < 1 or query.page_size < 1 or query.page_size > 100:
            raise ValidationError("Invalid pagination (page >= 1, 1 <= page_size <= 100).")
        today = today_iso()
        rows = personal_tasks(self._repository.find_by_type(ObjectType.TASK))

        def keep(obj) -> bool:
            meta = _meta(obj)
            if query.priority and (meta.get(KEY_PRIORITY) or "") != query.priority.strip().lower():
                return False
            if query.category and (meta.get(KEY_CATEGORY) or "") != query.category.strip().lower():
                return False
            if query.completed is not None and task_is_done(obj) != query.completed:
                return False
            if query.pinned is not None and is_true(meta.get(KEY_PINNED)) != query.pinned:
                return False
            if query.overdue is not None and task_is_overdue(obj, today) != query.overdue:
                return False
            due = meta.get(KEY_DUE_DATE) or ""
            if query.due_from and (not due or due < query.due_from):
                return False
            if query.due_to and (not due or due > query.due_to):
                return False
            haystack = " ".join(
                [obj.title, meta.get("description") or "", meta.get("tags") or "", meta.get("remarks") or ""]
            )
            return token_match(haystack, query.q)

        rows = [obj for obj in rows if keep(obj)]
        rows.sort(
            key=lambda obj: (
                0 if is_true(_meta(obj).get(KEY_PINNED)) else 1,
                1 if task_is_done(obj) else 0,
                _meta(obj).get(KEY_DUE_DATE) or "9999-12-31",
                obj.title.casefold(),
                str(obj.id),
            )
        )
        total = len(rows)
        start = (query.page - 1) * query.page_size
        page_items = [task_output(obj, today) for obj in rows[start : start + query.page_size]]
        return ListTasksResult(items=page_items, total_count=total, page=query.page, page_size=query.page_size)
