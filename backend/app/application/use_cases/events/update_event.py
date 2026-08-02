"""Use case: Update an Event — the frozen merge contract.

Mirrors ``UpdateProposalUseCase`` one-to-one: None = untouched, a provided
value replaces verbatim; tags/sections/registration/link groups are
group-replaces; a code/title/department/start_date change re-runs the
registry duplicate scan (409); replaced sections re-run
publication/document/speaker assertions (422, the schedule check resolves
against the EFFECTIVE speakers list); a presentations group-replace re-syncs
the derived publications edges.
"""
from __future__ import annotations

import json

from app.application.commands.update_event import UpdateEventCommand
from app.application.dtos.events import (
    KEY_CO_ORGANIZER,
    KEY_DEPARTMENT,
    KEY_DESCRIPTION,
    KEY_END_DATE,
    KEY_EVENT_CODE,
    KEY_EVENT_STATUS,
    KEY_EVENT_TYPE,
    KEY_MODE,
    KEY_NOTES,
    KEY_OBJECTIVES,
    KEY_ORGANIZER,
    KEY_OUTCOME,
    KEY_PRIORITY,
    KEY_REGISTRATION,
    KEY_SCHOOL,
    KEY_SPEAKERS,
    KEY_START_DATE,
    KEY_TAGS,
    KEY_VENUE,
    EventOutput,
    event_edge_group,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.events.create_event import (
    assert_document_refs,
    assert_link_targets,
    assert_publication_refs,
    assert_schedule_speakers,
    find_event_duplicates,
)
from app.application.use_cases.events.helpers import (
    SECTION_KEYS,
    SECTION_META_KEY,
    enrich_event_output,
    normalise_registration,
    normalise_section_rows,
    section_rows,
)
from app.application.validators.events import assert_valid_update_event_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class UpdateEventUseCase:
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

    def _type_of(self, target) -> ObjectType | None:
        found = self._repository.get_by_id(target)
        return found.object_type if found is not None else None

    def execute(self, command: UpdateEventCommand) -> EventOutput:
        data = command.input
        assert_valid_update_event_input(data)
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.EVENT:
            raise ObjectNotFoundError(f"Event {command.object_id} not found.")

        actor = data.actor.strip()
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        if any(
            value is not None
            for value in (data.title, data.event_code, data.department, data.start_date)
        ):
            duplicates = find_event_duplicates(
                self._repository,
                title=data.title if data.title is not None else obj.title,
                event_code=(
                    data.event_code
                    if data.event_code is not None
                    else meta.get(KEY_EVENT_CODE)
                ),
                department=(
                    data.department if data.department is not None else meta.get(KEY_DEPARTMENT)
                ),
                start_date=(
                    data.start_date
                    if data.start_date is not None
                    else meta.get(KEY_START_DATE)
                ),
                exclude_id=str(obj.id),
            )
            if duplicates:
                raise ObjectAlreadyExistsError(
                    f"Duplicate event: {duplicates[0].id} ({duplicates[0].title!r}) "
                    f"already carries this code / title+department+start_date."
                )

        # Section group-replaces are validated against live documents /
        # publications; the schedule's speaker rows resolve against the
        # EFFECTIVE speakers list (payload first, else the stored section).
        effective_speakers = (
            normalise_section_rows("speakers", list(data.speakers))
            if data.speakers is not None
            else section_rows(meta, KEY_SPEAKERS)
        )
        if data.participation is not None or data.speakers is not None:
            assert_document_refs(
                self._repository,
                list(data.participation) if data.participation is not None else [],
                list(data.speakers) if data.speakers is not None else [],
            )
        if data.presentations is not None:
            assert_publication_refs(self._repository, list(data.presentations))
        if data.schedule is not None:
            assert_schedule_speakers(list(data.schedule), effective_speakers)
        # Speakers replaced without touching the schedule: existing sessions
        # may dangle — tolerated on read (the DeleteVendor precedent), never
        # a write-time failure.

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_EVENT_CODE, data.event_code),
            (KEY_EVENT_TYPE, data.event_type),
            (KEY_ORGANIZER, data.organizer),
            (KEY_CO_ORGANIZER, data.co_organizer),
            (KEY_VENUE, data.venue),
            (KEY_MODE, data.mode),
            (KEY_START_DATE, data.start_date),
            (KEY_END_DATE, data.end_date),
            (KEY_DEPARTMENT, data.department),
            (KEY_SCHOOL, data.school),
            (KEY_DESCRIPTION, data.description),
            (KEY_OBJECTIVES, data.objectives),
            (KEY_OUTCOME, data.outcome),
            (KEY_EVENT_STATUS, data.event_status),
            (KEY_PRIORITY, data.priority),
            (KEY_NOTES, data.notes),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)

        if data.tags is not None:
            self._set(obj, KEY_TAGS, json.dumps(data.tags, ensure_ascii=False), actor)
        if data.registration is not None:
            self._set(
                obj,
                KEY_REGISTRATION,
                json.dumps(normalise_registration(data.registration), ensure_ascii=False),
                actor,
            )
        for section in SECTION_KEYS:
            payload = getattr(data, section)
            if payload is not None:
                rows = normalise_section_rows(section, list(payload))
                self._set(
                    obj, SECTION_META_KEY[section], json.dumps(rows, ensure_ascii=False), actor
                )

        # Link groups — group-replaces (the finance PART 7 precedent).
        link_payloads = {
            "faculty": data.faculty,
            "students": data.students,
            "projects": data.projects,
            "grants": data.grants,
            "committees": data.committees,
        }
        if data.presentations is not None:
            link_payloads["publications"] = [
                str(row["publication_id"]).strip()
                for row in data.presentations
                if row.get("publication_id")
            ]
        for group, raw in link_payloads.items():
            if raw is None:
                continue
            new_ids = {ObjectId.parse(item) for item in raw}
            assert_link_targets(self._repository, group, sorted(new_ids, key=str))
            existing = {
                rel.target: rel
                for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
                and event_edge_group(rel.kind, self._type_of(rel.target)) == group
            }
            for target, _rel in list(existing.items()):
                if target not in new_ids:
                    obj.remove_relationship(target, RelationshipKind.RELATED_TO, actor=actor)
            for target_id in sorted(new_ids, key=str):
                if target_id not in existing:
                    obj.add_relationship(
                        target_id, RelationshipKind.RELATED_TO, Provenance.ASSERTED, actor=actor
                    )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        link_ids = [
            rel.target for rel in obj.relationships
            if rel.kind is RelationshipKind.RELATED_TO
        ]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
        output = EventOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        enrich_event_output(self._repository, obj, output)
        return output

