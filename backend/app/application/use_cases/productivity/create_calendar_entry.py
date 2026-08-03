"""Use case: Create a personal calendar entry (PART 2 tail)."""
from __future__ import annotations

import json

from app.application.commands.create_calendar_entry import CreateCalendarEntryCommand
from app.application.dtos.productivity import (
    KEY_CATEGORY,
    KEY_DESCRIPTION,
    KEY_END_DATE,
    KEY_END_TIME,
    KEY_LOCATION,
    KEY_START_DATE,
    KEY_START_TIME,
    KEY_TAGS,
    EntryOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import entry_output
from app.application.validators.productivity import assert_valid_create_entry_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class CreateCalendarEntryUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateCalendarEntryCommand) -> EntryOutput:
        data = command.input
        assert_valid_create_entry_input(data)

        title_cf = data.title.strip().casefold()
        for existing in self._repository.find_by_type(ObjectType.CALENDAR_ENTRY):
            other = {entry.key: entry.value for entry in existing.metadata.entries}
            if (
                existing.title.casefold() == title_cf
                and (other.get(KEY_START_DATE) or "") == data.start_date.strip()
            ):
                raise ObjectAlreadyExistsError(
                    f"A calendar entry '{data.title.strip()}' already exists on {data.start_date.strip()}."
                )

        actor = data.uploaded_by.strip()
        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_DESCRIPTION, data.description)
        put(KEY_START_DATE, data.start_date)
        put(KEY_END_DATE, data.end_date)
        put(KEY_START_TIME, data.start_time)
        put(KEY_END_TIME, data.end_time)
        put(KEY_LOCATION, data.location)
        put(KEY_CATEGORY, (data.category or "").strip().lower() or None)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False) if data.tags else None)

        obj = UniversalObject.create(
            object_type=ObjectType.CALENDAR_ENTRY,
            title=data.title.strip(),
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return entry_output(obj, events)
