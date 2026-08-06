"""Use case: Register an Event (PART 1 record + PARTS 2-5 sections + PART 8
publication links + people/research/governance link groups).

Mirrors ``CreateProposalUseCase``: validate -> duplicate scan (event code;
title+department+start_date triple, 409) -> link target assertions (422) ->
publication/document/speaker reference assertions (422) -> L6 metadata
record -> RELATED_TO edges on the event aggregate -> persist -> events ->
enriched output (one shared enrichment helper, no copies).
"""
from __future__ import annotations

import json

from app.application.commands.create_event import CreateEventCommand
from app.application.dtos.events import (
    EVENT_GROUP_TARGET_TYPE,
    EVENT_INPUT_LINK_GROUPS,
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
    KEY_START_DATE,
    KEY_TAGS,
    KEY_VENUE,
    EventOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.services.graph_integrity import assert_edge_targets
from app.application.use_cases.events.helpers import (
    SECTION_KEYS,
    SECTION_META_KEY,
    enrich_event_output,
    normalise_registration,
    normalise_section_rows,
)
from app.application.validators.events import assert_valid_create_event_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def find_event_duplicates(
    repository: ObjectRepository,
    *,
    title: str | None,
    event_code: str | None,
    department: str | None,
    start_date: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: event code, else the
    (title, department, start_date) triple."""
    wanted_code = (event_code or "").strip().casefold()
    wanted_title = (title or "").strip().casefold()
    wanted_dept = (department or "").strip().casefold()
    wanted_date = (start_date or "").strip()
    if not (wanted_code or wanted_title):
        return []
    matches: list[UniversalObject] = []
    for obj in repository.find_by_type(ObjectType.EVENT):
        if exclude_id is not None and str(obj.id) == exclude_id:
            continue
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        if wanted_code and (
            meta.get(KEY_EVENT_CODE) or ""
        ).strip().casefold() == wanted_code:
            matches.append(obj)
            continue
        if (
            wanted_title
            and wanted_date
            and obj.title.strip().casefold() == wanted_title
            and (meta.get(KEY_DEPARTMENT) or "").strip().casefold() == wanted_dept
            and (meta.get(KEY_START_DATE) or "").strip() == wanted_date
        ):
            matches.append(obj)
    return matches


def assert_link_targets(
    repository: ObjectRepository, group: str, ids: list[ObjectId]
) -> None:
    """Linked Objects must exist and carry the group's expected type (422)."""
    expected = EVENT_GROUP_TARGET_TYPE[group]
    for target_id in ids:
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Linked object {target_id} not found.")
        if target.object_type is not expected:
            raise ValidationError(
                f"{group} expects {expected.value} targets; {target_id} is a "
                f"{target.object_type.value}."
            )


def assert_publication_refs(repository: ObjectRepository, rows: list[dict]) -> None:
    """Every presentation publication_id must be a live PUBLICATION (422)."""
    for row in rows:
        raw = row.get("publication_id")
        if raw in (None, ""):
            continue  # presence is enforced by the validators
        target_id = ObjectId.parse(str(raw).strip())
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Publication {target_id} not found.")
        if target.object_type is not ObjectType.PUBLICATION:
            raise ValidationError(
                f"publication_id must reference a publication object; {target_id} is a "
                f"{target.object_type.value}."
            )


def assert_document_refs(
    repository: ObjectRepository,
    participation: list[dict],
    speakers: list[dict],
) -> None:
    """Certificate / photo / supporting document ids must resolve to live
    DOCUMENT Objects (422)."""
    ids: list[str] = []
    for row in participation:
        if row.get("certificate_document_id"):
            ids.append(str(row["certificate_document_id"]))
    for row in speakers:
        if row.get("photo_document_id"):
            ids.append(str(row["photo_document_id"]))
        ids.extend(str(raw) for raw in row.get("document_ids") or [])
    for raw in ids:
        target_id = ObjectId.parse(raw.strip())
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Document {target_id} not found.")
        if target.object_type is not ObjectType.DOCUMENT:
            raise ValidationError(
                f"document references must point at document objects; {target_id} is a "
                f"{target.object_type.value}."
            )


def assert_schedule_speakers(schedule: list[dict], speakers: list[dict]) -> None:
    """Every session speaker_id must reference a speaker row of THIS event."""
    known = {
        str(row.get("row_id"))
        for row in speakers
        if row.get("row_id")
    }
    for index, row in enumerate(schedule, start=1):
        raw = (row.get("speaker_id") or "").strip()
        if raw and raw not in known:
            raise ValidationError(
                f"schedule row {index} speaker_id {raw!r} does not match any speaker "
                f"of this event."
            )


class CreateEventUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateEventCommand) -> EventOutput:
        data = command.input
        assert_valid_create_event_input(data)

        duplicates = find_event_duplicates(
            self._repository,
            title=data.title,
            event_code=data.event_code,
            department=data.department,
            start_date=data.start_date,
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate event: {existing.id} ({existing.title!r}) already carries "
                f"this code / title+department+start_date."
            )

        link_ids: dict[str, list[ObjectId]] = {}
        for group in EVENT_INPUT_LINK_GROUPS:
            raw_ids = list(getattr(data, group) or [])
            ids = [ObjectId.parse(raw) for raw in raw_ids]
            assert_link_targets(self._repository, group, ids)
            link_ids[group] = ids

        sections = {
            section: normalise_section_rows(section, list(getattr(data, section) or []))
            for section in SECTION_KEYS
        }
        registration = normalise_registration(data.registration)
        assert_publication_refs(self._repository, sections["presentations"])
        assert_document_refs(
            self._repository, sections["participation"], sections["speakers"]
        )
        assert_schedule_speakers(sections["schedule"], sections["speakers"])

        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_EVENT_CODE, data.event_code)
        put(KEY_EVENT_TYPE, data.event_type or "custom")
        put(KEY_ORGANIZER, data.organizer)
        put(KEY_CO_ORGANIZER, data.co_organizer)
        put(KEY_VENUE, data.venue)
        put(KEY_MODE, data.mode)
        put(KEY_START_DATE, data.start_date)
        put(KEY_END_DATE, data.end_date)
        put(KEY_DEPARTMENT, data.department)
        put(KEY_SCHOOL, data.school)
        put(KEY_DESCRIPTION, data.description)
        put(KEY_OBJECTIVES, data.objectives)
        put(KEY_OUTCOME, data.outcome)
        put(KEY_EVENT_STATUS, data.event_status or "planned")
        put(KEY_PRIORITY, data.priority)
        put(KEY_NOTES, data.notes)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False) if data.tags else None)
        for section in SECTION_KEYS:
            if sections[section]:
                put(SECTION_META_KEY[section], json.dumps(sections[section], ensure_ascii=False))
        if any(registration.values()):
            put(KEY_REGISTRATION, json.dumps(registration, ensure_ascii=False))

        obj = UniversalObject.create(
            object_type=ObjectType.EVENT,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        all_link_ids: list[ObjectId] = []
        link_targets: list[tuple[ObjectId, object]] = []
        for group in EVENT_INPUT_LINK_GROUPS:
            for target_id in link_ids[group]:
                link_targets.append((target_id, EVENT_GROUP_TARGET_TYPE.get(group)))
        for row in sections["presentations"]:
            target_id = ObjectId.parse(str(row["publication_id"]).strip())
            link_targets.append((target_id, ObjectType.PUBLICATION))
        assert_edge_targets(
            self._repository, link_targets, source_id=obj.id, label="linked"
        )
        for target_id, _ in link_targets:
            obj.add_relationship(
                target_id, RelationshipKind.RELATED_TO, Provenance.ASSERTED,
                actor=data.created_by.strip(),
            )
            all_link_ids.append(target_id)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_link_ids)}
        output = EventOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        enrich_event_output(self._repository, obj, output)
        return output
