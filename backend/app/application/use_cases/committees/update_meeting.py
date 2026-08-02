"""Use case: Update a Meeting — the frozen merge contract (verbatim replace).

Mirrors ``UpdateMeetingUseCase`` semantics from the milestone doctrine:
None = untouched; provided values replace (agenda/attendance/decisions are
whole-list group-replaces); a meeting-number change re-runs the per-committee
uniqueness scan (409).
"""
from __future__ import annotations

import json

from app.application.commands.update_meeting import UpdateMeetingCommand
from app.application.dtos.committee import (
    KEY_AGENDA_ITEMS,
    KEY_ATTENDANCE,
    KEY_DECISIONS,
    KEY_MEETING_DATE,
    KEY_MEETING_NUMBER,
    KEY_MINUTES,
    KEY_MODE,
    KEY_REMARKS,
    KEY_VENUE,
    MeetingOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.queries.get_meeting import GetMeetingQuery
from app.application.use_cases.committees.add_meeting import find_meeting_number_duplicates
from app.application.use_cases.committees.get_meeting import GetMeetingUseCase
from app.application.validators.committee import assert_valid_update_meeting_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateMeetingUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def _set(self, obj: UniversalObject, key: str, value: str, actor: str) -> None:
        if obj.metadata.get_value(key) != value:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

    def execute(self, command: UpdateMeetingCommand) -> MeetingOutput:
        data = command.input
        assert_valid_update_meeting_input(data)

        obj = self._repository.get_by_id(command.meeting_id)
        if obj is None or obj.object_type is not ObjectType.MEETING:
            raise ObjectNotFoundError(f"Meeting {command.meeting_id} not found.")

        actor = data.actor.strip()

        if data.meeting_number is not None:
            committee_id = next(
                (str(rel.target) for rel in obj.relationships
                 if rel.kind is RelationshipKind.BELONGS_TO),
                None,
            )
            if committee_id is not None:
                duplicates = find_meeting_number_duplicates(
                    self._repository, committee_id, data.meeting_number,
                    exclude_id=str(obj.id),
                )
                if duplicates:
                    raise ObjectAlreadyExistsError(
                        f"Duplicate meeting number: {duplicates[0].id} ({duplicates[0].title!r}) "
                        f"already carries number {data.meeting_number!r} in this committee."
                    )

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        for key, value in (
            (KEY_MEETING_NUMBER, data.meeting_number),
            (KEY_MEETING_DATE, data.meeting_date),
            (KEY_VENUE, data.venue),
            (KEY_MINUTES, data.minutes),
            (KEY_REMARKS, data.remarks),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)
        if data.mode is not None:
            self._set(obj, KEY_MODE, data.mode.strip().lower(), actor)

        if data.agenda_items is not None:
            self._set(obj, KEY_AGENDA_ITEMS, json.dumps(data.agenda_items, ensure_ascii=False), actor)
        if data.attendance is not None:
            self._set(obj, KEY_ATTENDANCE, json.dumps(data.attendance, ensure_ascii=False), actor)
        if data.decisions is not None:
            self._set(obj, KEY_DECISIONS, json.dumps(data.decisions, ensure_ascii=False), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        output = GetMeetingUseCase(self._repository).execute(
            GetMeetingQuery(meeting_id=str(obj.id))
        )
        output.events = [getattr(event, "name", str(event)) for event in events]
        return output
