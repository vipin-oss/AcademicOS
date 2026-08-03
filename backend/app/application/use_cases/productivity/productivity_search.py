"""Use case: Unified Productivity search (PART 7) — tasks + notifications +
the aggregated feed, all server-side, combinable filters."""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_CATEGORY,
    KEY_PRIORITY,
    ProductivitySearchResult,
    SearchHitOutput,
)
from app.application.exceptions import ValidationError
from app.application.queries.productivity_search import ProductivitySearchQuery
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    _meta,
    add_days,
    build_calendar_feed,
    personal_tasks,
    today_iso,
    token_match,
)
from app.application.validators.productivity import assert_search_window
from app.domain.repositories.object_repository import ObjectRepository


class ProductivitySearchUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ProductivitySearchQuery) -> ProductivitySearchResult:
        assert_search_window(query.date_from, query.date_to)
        if query.limit < 1 or query.limit > 100:
            raise ValidationError("limit must be between 1 and 100.")
        source = (query.source or "").strip().lower() or None
        if source is not None and source not in ("tasks", "notifications", "calendar"):
            raise ValidationError("source must be one of: tasks, notifications, calendar.")
        today = today_iso()
        snapshot = ProductivitySnapshot(self._repository)
        hits: list[SearchHitOutput] = []

        priority = (query.priority or "").strip().lower() or None
        category = (query.category or "").strip().lower() or None

        def date_ok(day: str | None) -> bool:
            if query.date_from and (not day or day < query.date_from):
                return False
            if query.date_to and (not day or day > query.date_to):
                return False
            return True

        if source in (None, "tasks"):
            for obj in personal_tasks(snapshot.tasks_all):
                meta = _meta(obj)
                if priority and (meta.get(KEY_PRIORITY) or "") != priority:
                    continue
                if category and (meta.get(KEY_CATEGORY) or "") != category:
                    continue
                anchor = meta.get("due_date") or meta.get("start_date")
                if not date_ok(anchor):
                    continue
                haystack = " ".join(
                    [obj.title, meta.get("description") or "", meta.get("tags") or "", meta.get("remarks") or ""]
                )
                if not token_match(haystack, query.q):
                    continue
                hits.append(
                    SearchHitOutput(
                        id=f"tasks:{obj.id}",
                        source="tasks",
                        kind="task",
                        title=obj.title,
                        date=anchor,
                        priority=meta.get(KEY_PRIORITY),
                        category=meta.get(KEY_CATEGORY),
                        snippet=meta.get("description"),
                        href="/productivity",
                    )
                )

        if source in (None, "notifications"):
            for obj in snapshot.notifications:
                meta = _meta(obj)
                if priority and (meta.get(KEY_PRIORITY) or "") != priority:
                    continue
                if category and (meta.get(KEY_CATEGORY) or "") != category:
                    continue
                anchor = (obj.audit.created_at.date().isoformat() if obj.audit else None)
                if not date_ok(anchor):
                    continue
                haystack = " ".join([obj.title, meta.get("body") or ""])
                if not token_match(haystack, query.q):
                    continue
                hits.append(
                    SearchHitOutput(
                        id=f"notifications:{obj.id}",
                        source="notifications",
                        kind="notification",
                        title=obj.title,
                        date=anchor,
                        priority=meta.get(KEY_PRIORITY),
                        category=meta.get(KEY_CATEGORY),
                        snippet=meta.get("body"),
                        href=meta.get("link") or "/productivity",
                    )
                )

        if source in (None, "calendar"):
            win_from = query.date_from or add_days(today, -365)
            win_to = query.date_to or add_days(today, 365)
            feed = build_calendar_feed(snapshot, win_from, win_to, None, today)
            for item in feed:
                if priority and (item.priority or "") != priority:
                    continue
                if category and item.source != category:
                    continue  # feed has no category col; source acts as its group
                if not token_match(f"{item.title} {item.subtitle or ''}", query.q):
                    continue
                hits.append(
                    SearchHitOutput(
                        id=item.id,
                        source=item.source,
                        kind=item.kind,
                        title=item.title,
                        date=item.date,
                        priority=item.priority,
                        category=item.source,
                        snippet=item.subtitle,
                        href=item.href,
                    )
                )

        hits.sort(key=lambda h: (h.date or "9999-12-31", h.title.casefold(), h.id))
        total = len(hits)
        return ProductivitySearchResult(items=hits[: query.limit], total_count=total)
