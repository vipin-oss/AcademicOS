"""Use case: Productivity Hub dashboard (PART 6 cards)."""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_COMPLETION_DATE,
    KEY_DUE_DATE,
    ProductivityDashboardOutput,
)
from app.application.queries.get_productivity_dashboard import (
    GetProductivityDashboardQuery,
)
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    _meta,
    add_days,
    build_calendar_feed,
    build_reminders,
    personal_tasks,
    task_is_done,
    today_iso,
    unread_count,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetProductivityDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetProductivityDashboardQuery) -> ProductivityDashboardOutput:
        today = today_iso(query.as_of)
        snapshot = ProductivitySnapshot(self._repository)
        week_end = add_days(today, 7)

        tasks = personal_tasks(snapshot.tasks_all)
        todays_tasks = sum(
            1
            for obj in tasks
            if not task_is_done(obj) and (_meta(obj).get(KEY_DUE_DATE) or "") == today
        )
        completed_today = sum(
            1 for obj in tasks if (_meta(obj).get(KEY_COMPLETION_DATE) or "") == today
        )

        buckets = build_reminders(snapshot, today)
        upcoming_deadlines = len(buckets["tomorrow"]) + len(buckets["this_week"])
        overdue_items = len(buckets["overdue"])

        meetings_feed = build_calendar_feed(
            snapshot, today, week_end, ("events", "committee_meetings"), today
        )
        upcoming_meetings = len(meetings_feed)

        return ProductivityDashboardOutput(
            todays_tasks=todays_tasks,
            upcoming_deadlines=upcoming_deadlines,
            upcoming_meetings=upcoming_meetings,
            unread_notifications=unread_count(snapshot.notifications, today),
            overdue_items=overdue_items,
            completed_today=completed_today,
        )
