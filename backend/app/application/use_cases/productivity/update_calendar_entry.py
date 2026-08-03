"""Use case: Update a personal calendar entry (verbatim merge semantics)."""
from __future__ import annotations

import json

from app.application.commands.update_calendar_entry import UpdateCalendarEntryCommand
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
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import entry_output
from app.application.validators.productivity import assert_valid_update_entry_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateCalendarEntryUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UpdateCalendarEntryCommand) -> EntryOutput:
        data = command.input
        assert_valid_update_entry_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.CALENDAR_ENTRY:
            raise ObjectNotFoundError(f"Calendar entry {command.object_id} not found.")

        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        merged_start = data.start_date if data.start_date is not None else meta.get(KEY_START_DATE)
        merged_end = data.end_date if data.end_date is not None else meta.get(KEY_END_DATE)
        if merged_start and merged_end and str(merged_start) > str(merged_end):
            raise ValidationError("start_date must not be after end_date.")
        merged_start_t = data.start_time if data.start_time is not None else meta.get(KEY_START_TIME)
        merged_end_t = data.end_time if data.end_time is not None else meta.get(KEY_END_TIME)
        if merged_start_t and merged_end_t and str(merged_start_t) > str(merged_end_t):
            raise ValidationError("start_time must not be after end_time.")

        actor = (data.uploaded_by or "system").strip() or "system"

        def set_if_provided(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            obj.set_metadata(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

        if data.title is not None:
            obj.rename(data.title.strip(), actor=actor)
        set_if_provided(KEY_DESCRIPTION, data.description)
        set_if_provided(KEY_START_DATE, data.start_date)
        set_if_provided(KEY_END_DATE, data.end_date)
        set_if_provided(KEY_START_TIME, data.start_time)
        set_if_provided(KEY_END_TIME, data.end_time)
        set_if_provided(KEY_LOCATION, data.location)
        set_if_provided(KEY_CATEGORY, data.category.strip().lower() if data.category else None)
        if data.tags is not None:
            set_if_provided(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False))

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return entry_output(obj, events)
