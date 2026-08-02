"""Use case: Add a Meeting to a Committee (PART 3).

A meeting is a ``meeting`` Universal Object (BELONGS_TO → the committee)
carrying number/date/venue/mode/agenda/minutes/attendance/decisions/remarks
as L6 human-asserted metadata — the ``project_milestone`` doctrine verbatim.
``meeting_number`` is unique per committee (409).
"""
from __future__ import annotations

import json

from app.application.commands.add_meeting import AddMeetingCommand
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
from app.application.use_cases.committees.helpers import meetings_of_committee
from app.application.validators.committee import assert_valid_create_meeting_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


def find_meeting_number_duplicates(
    repository: ObjectRepository,
    committee_id: str,
    meeting_number: str,
    *,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Meeting numbers are unique within their committee (case-insensitive)."""
    wanted = (meeting_number or "").strip().casefold()
    if not wanted:
        return []
    matches = []
    for meeting in meetings_of_committee(repository, committee_id):
        if exclude_id is not None and str(meeting.id) == exclude_id:
            continue
        number = (
            {entry.key: entry.value for entry in meeting.metadata.entries}.get(KEY_MEETING_NUMBER)
            or ""
        ).strip().casefold()
        if number == wanted:
            matches.append(meeting)
    return matches


class AddMeetingUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: AddMeetingCommand) -> MeetingOutput:
        data = command.input
        assert_valid_create_meeting_input(data)

        committee = self._repository.get_by_id(command.committee_id)
        if committee is None or committee.object_type is not ObjectType.COMMITTEE:
            raise ObjectNotFoundError(f"Committee {command.committee_id} not found.")

        if data.meeting_number:
            duplicates = find_meeting_number_duplicates(
                self._repository, command.committee_id, data.meeting_number
            )
            if duplicates:
                raise ObjectAlreadyExistsError(
                    f"Duplicate meeting number: {duplicates[0].id} ({duplicates[0].title!r}) "
                    f"already carries number {data.meeting_number!r} in this committee."
                )

        actor = (command.actor or "system").strip() or "system"
        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(
                    key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                )
            )

        put(KEY_MEETING_NUMBER, data.meeting_number)
        put(KEY_MEETING_DATE, data.meeting_date)
        put(KEY_VENUE, data.venue)
        put(KEY_MODE, (data.mode or "").strip().lower() or None)
        put(KEY_MINUTES, data.minutes)
        put(KEY_REMARKS, data.remarks)
        if data.agenda_items:
            put(KEY_AGENDA_ITEMS, json.dumps(data.agenda_items, ensure_ascii=False))
        if data.attendance:
            put(KEY_ATTENDANCE, json.dumps(data.attendance, ensure_ascii=False))
        if data.decisions:
            put(KEY_DECISIONS, json.dumps(data.decisions, ensure_ascii=False))

        obj = UniversalObject.create(
            object_type=ObjectType.MEETING,
            title=data.title.strip(),
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        obj.add_relationship(
            committee.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        output = MeetingOutput.from_domain(obj, events, linked_by_id={str(committee.id): committee})
        output.action_items = []
        output.stats = {"agenda_items": len(output.agenda_items), "pending_actions": 0, "completed_actions": 0}
        return output
