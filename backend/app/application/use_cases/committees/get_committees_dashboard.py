"""Use case: the PART 8 Committees & Meetings dashboard (computed read).

Mirrors ``GetResearchDashboardUseCase``: every number is derived by scanning
the graph at read time — no stored counters, no duplication:

  total / active committees   object scan (status)
  meetings this month         meeting_date within the current YYYY-MM
  pending / completed actions task children of every committee meeting
  upcoming meetings           meeting_date >= today, ascending, with the
                              committee title denormalised (limit-capped)
"""
from __future__ import annotations

import datetime as _dt

from app.application.dtos.committee import (
    KEY_ACTION_STATUS,
    KEY_MEETING_DATE,
    KEY_MEETING_NUMBER,
    KEY_MODE,
    KEY_VENUE,
    CommitteesDashboard,
)
from app.application.queries.get_committees_dashboard import GetCommitteesDashboardQuery
from app.application.use_cases.committees.helpers import (
    actions_of_meeting,
    meetings_of_committee,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType


class GetCommitteesDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCommitteesDashboardQuery) -> CommitteesDashboard:
        today = _dt.datetime.now(_dt.UTC).date().isoformat()
        this_month = today[:7]  # YYYY-MM

        committees = self._repository.find_by_type(ObjectType.COMMITTEE)
        total = len(committees)
        active = sum(1 for obj in committees if obj.status is ObjectStatus.ACTIVE)

        meetings_this_month = 0
        pending_actions = 0
        completed_actions = 0
        upcoming: list[dict] = []

        for committee in committees:
            for meeting in meetings_of_committee(self._repository, str(committee.id)):
                meta = {entry.key: entry.value for entry in meeting.metadata.entries}
                date = (meta.get(KEY_MEETING_DATE) or "").strip()
                if date.startswith(this_month):
                    meetings_this_month += 1
                if date and date >= today and meeting.status is ObjectStatus.ACTIVE:
                    upcoming.append(
                        {
                            "meeting_id": str(meeting.id),
                            "committee_id": str(committee.id),
                            "committee_title": committee.title,
                            "title": meeting.title,
                            "meeting_number": meta.get(KEY_MEETING_NUMBER),
                            "date": date,
                            "venue": meta.get(KEY_VENUE),
                            "mode": meta.get(KEY_MODE),
                        }
                    )
                for action in actions_of_meeting(self._repository, str(meeting.id)):
                    status = (
                        {e.key: e.value for e in action.metadata.entries}.get(KEY_ACTION_STATUS)
                        or "pending"
                    )
                    if status == "done":
                        completed_actions += 1
                    else:
                        pending_actions += 1

        upcoming.sort(
            key=lambda item: (item["date"], item["title"].casefold(), item["meeting_id"])
        )
        limit = max(1, min(int(query.upcoming_limit or 10), 50))
        return CommitteesDashboard(
            total_committees=total,
            active_committees=active,
            meetings_this_month=meetings_this_month,
            pending_actions=pending_actions,
            completed_actions=completed_actions,
            upcoming_meetings=upcoming[:limit],
        )
