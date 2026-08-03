"""Use case: Notification Center list (PART 4 states + filters).

State semantics: ``None`` (default) = the active set (unarchived, not
currently snoozed); ``unread``/``read``/``pinned`` narrow the active set;
``snoozed`` and ``archived`` select those shelves; ``all`` shows everything.
``unread_count`` is always the active-set unread total (PART 6 feeds).
Ordering: pinned first, then newest.
"""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_CATEGORY,
    KEY_IS_READ,
    KEY_PINNED,
    KEY_PRIORITY,
    KEY_SOURCE_MODULE,
    ListNotificationsResult,
)
from app.application.exceptions import ValidationError
from app.application.queries.list_notifications import ListNotificationsQuery
from app.application.use_cases.productivity.helpers import (
    _meta,
    is_true,
    notification_output,
    today_iso,
    token_match,
    unread_count,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType

_STATES = ("unread", "read", "pinned", "archived", "snoozed", "all")


class ListNotificationsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListNotificationsQuery) -> ListNotificationsResult:
        state = (query.state or "").strip().lower() or None
        if state is not None and state not in _STATES:
            raise ValidationError(f"state must be one of: {', '.join(_STATES)}.")
        if query.page < 1 or query.page_size < 1 or query.page_size > 100:
            raise ValidationError("Invalid pagination (page >= 1, 1 <= page_size <= 100).")
        today = today_iso()
        rows = self._repository.find_by_type(ObjectType.NOTIFICATION)

        def keep(obj) -> bool:
            meta = _meta(obj)
            archived = is_true(meta.get("archived"))
            snoozed = notification_output_snoozed(meta, today)
            active = not archived and not snoozed
            if state == "archived" and not archived:
                return False
            if state == "snoozed" and not (snoozed and not archived):
                return False
            if state in (None, "unread", "read", "pinned") and not active:
                return False
            if state == "unread" and is_true(meta.get(KEY_IS_READ)):
                return False
            if state == "read" and not is_true(meta.get(KEY_IS_READ)):
                return False
            if state == "pinned" and not is_true(meta.get(KEY_PINNED)):
                return False
            if query.priority and (meta.get(KEY_PRIORITY) or "") != query.priority.strip().lower():
                return False
            if query.category and (meta.get(KEY_CATEGORY) or "") != query.category.strip().lower():
                return False
            if query.source_module and (meta.get(KEY_SOURCE_MODULE) or "") != query.source_module.strip().lower():
                return False
            haystack = " ".join([obj.title, meta.get("body") or ""])
            return token_match(haystack, query.q)

        rows = [obj for obj in rows if keep(obj)]
        # Pinned-first, newest inside each group (two-pass stable sort).
        rows.sort(key=lambda obj: (obj.audit.created_at if obj.audit else "", str(obj.id)), reverse=True)
        rows.sort(key=lambda obj: 0 if is_true(_meta(obj).get(KEY_PINNED)) else 1)
        total = len(rows)
        start = (query.page - 1) * query.page_size
        page_items = [notification_output(obj, today) for obj in rows[start : start + query.page_size]]
        return ListNotificationsResult(
            items=page_items,
            total_count=total,
            page=query.page,
            page_size=query.page_size,
            unread_count=unread_count(self._repository.find_by_type(ObjectType.NOTIFICATION), today),
        )


def notification_output_snoozed(meta: dict[str, str], today: str) -> bool:
    snoozed_until = meta.get("snoozed_until")
    return bool(snoozed_until) and str(snoozed_until) >= today
