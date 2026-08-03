"""Use case: Aggregated calendar window feed (PART 1 + PART 2)."""
from __future__ import annotations

from app.application.dtos.productivity import (
    CALENDAR_SOURCE_CODES,
    CalendarFeedResult,
)
from app.application.exceptions import ValidationError
from app.application.queries.get_calendar_feed import GetCalendarFeedQuery
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    build_calendar_feed,
    today_iso,
)
from app.application.validators.productivity import assert_calendar_window
from app.domain.repositories.object_repository import ObjectRepository


class GetCalendarFeedUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCalendarFeedQuery) -> CalendarFeedResult:
        assert_calendar_window(query.date_from, query.date_to)
        if query.sources:
            unknown = [s for s in query.sources if s not in CALENDAR_SOURCE_CODES]
            if unknown:
                raise ValidationError(
                    f"Unknown calendar source(s): {', '.join(unknown)} "
                    f"(allowed: {', '.join(CALENDAR_SOURCE_CODES)})."
                )
        snapshot = ProductivitySnapshot(self._repository)
        items = build_calendar_feed(
            snapshot, query.date_from, query.date_to, query.sources, today_iso()
        )
        used = list(query.sources) if query.sources else list(CALENDAR_SOURCE_CODES)
        return CalendarFeedResult(
            items=items, date_from=query.date_from, date_to=query.date_to, sources=used
        )
