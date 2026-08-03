"""Use case: Get one personal calendar entry."""
from __future__ import annotations

from app.application.dtos.productivity import EntryOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_calendar_entry import GetCalendarEntryQuery
from app.application.use_cases.productivity.helpers import entry_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetCalendarEntryUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCalendarEntryQuery) -> EntryOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.CALENDAR_ENTRY:
            raise ObjectNotFoundError(f"Calendar entry {query.object_id} not found.")
        return entry_output(obj)
