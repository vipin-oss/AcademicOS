"""Use case: Reminder engine buckets (PART 5)."""
from __future__ import annotations

import datetime as dt

from app.application.dtos.productivity import RemindersResult
from app.application.queries.get_reminders import GetRemindersQuery
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    build_reminders,
    today_iso,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetRemindersUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetRemindersQuery) -> RemindersResult:
        today = today_iso(query.as_of)
        snapshot = ProductivitySnapshot(self._repository)
        buckets = build_reminders(snapshot, today)
        return RemindersResult(
            overdue=buckets["overdue"],
            due_today=buckets["due_today"],
            upcoming_today=buckets["upcoming_today"],
            tomorrow=buckets["tomorrow"],
            this_week=buckets["this_week"],
            generated_at=dt.datetime.now(dt.UTC).isoformat(),
        )
