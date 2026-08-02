"""Use case: Events & Academic Activities dashboard cards (PART 9).

Computed read (the finance dashboard precedent) — no stored counters.
"""
from __future__ import annotations

from app.application.dtos.events import EventsDashboard
from app.application.queries.get_events_dashboard import GetEventsDashboardQuery
from app.application.use_cases.events.helpers import events_dashboard
from app.domain.repositories.object_repository import ObjectRepository


class GetEventsDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetEventsDashboardQuery) -> EventsDashboard:
        cards = events_dashboard(self._repository)
        return EventsDashboard(
            upcoming_events=cards["upcoming_events"],
            completed_events=cards["completed_events"],
            events_organized=cards["events_organized"],
            events_attended=cards["events_attended"],
            certificates=cards["certificates"],
            presentations=cards["presentations"],
            invited_talks=cards["invited_talks"],
        )
