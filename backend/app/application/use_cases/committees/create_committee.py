"""Use case: Register a Committee (PART 1 directory + PART 2 members + links).

Mirrors ``CreateFacultyUseCase``/``CreateProjectUseCase``: validate ->
duplicate check (committee code; name+type+department triple, 409) -> link
target assertions (422) -> member person assertions (422) -> L6 metadata
record -> RELATED_TO edges (on the committee) -> MEMBER_OF backlinks (on the
member aggregates, research-team precedent) -> persist -> events -> output.
"""
from __future__ import annotations

import json

from app.application.commands.create_committee import CreateCommitteeCommand
from app.application.dtos.committee import (
    COMMITTEE_GROUP_TARGET_TYPE,
    COMMITTEE_LINK_GROUPS,
    KEY_COMMITTEE_CODE,
    KEY_COMMITTEE_TYPE,
    KEY_CONSTITUTION_DATE,
    KEY_DEPARTMENT,
    KEY_DESCRIPTION,
    KEY_EXPIRY_DATE,
    KEY_MEMBERS,
    KEY_NOTES,
    KEY_SCHOOL,
    KEY_TAGS,
    CommitteeOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.committees.helpers import enrich_committee_output
from app.application.validators.committee import assert_valid_create_committee_input
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


def find_committee_duplicates(
    repository: ObjectRepository,
    *,
    name: str | None,
    committee_code: str | None,
    committee_type: str | None,
    department: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: code, else the (name, type, department) triple."""
    wanted_code = (committee_code or "").strip().casefold()
    wanted_name = (name or "").strip().casefold()
    wanted_type = (committee_type or "").strip().casefold()
    wanted_dept = (department or "").strip().casefold()
    if not (wanted_code or wanted_name):
        return []
    matches: list[UniversalObject] = []
    for obj in repository.find_by_type(ObjectType.COMMITTEE):
        if exclude_id is not None and str(obj.id) == exclude_id:
            continue
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        if wanted_code and (meta.get(KEY_COMMITTEE_CODE) or "").strip().casefold() == wanted_code:
            matches.append(obj)
            continue
        if (
            wanted_name
            and obj.title.strip().casefold() == wanted_name
            and (meta.get(KEY_COMMITTEE_TYPE) or "").strip().casefold() == wanted_type
            and (meta.get(KEY_DEPARTMENT) or "").strip().casefold() == wanted_dept
        ):
            matches.append(obj)
    return matches


def assert_link_targets(
    repository: ObjectRepository, group: str, ids: list[ObjectId]
) -> None:
    """Linked Objects must exist and carry the group's expected type (422)."""
    expected = COMMITTEE_GROUP_TARGET_TYPE[group]
    for target_id in ids:
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Linked object {target_id} not found.")
        if target.object_type is not expected:
            raise ValidationError(
                f"{group} expects {expected.value} targets; {target_id} is a "
                f"{target.object_type.value}."
            )


def assert_member_persons(repository: ObjectRepository, members: list[dict]) -> None:
    """Members must resolve to live FACULTY/STUDENT Objects (422)."""
    for member in members:
        target_id = ObjectId.parse(str(member["faculty_id"]).strip())
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Member {target_id} not found.")
        if target.object_type not in (ObjectType.FACULTY, ObjectType.STUDENT):
            raise ValidationError(
                f"Member {target_id} must be a faculty or student object; it is a "
                f"{target.object_type.value}."
            )


class CreateCommitteeUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateCommitteeCommand) -> CommitteeOutput:
        data = command.input
        assert_valid_create_committee_input(data)

        duplicates = find_committee_duplicates(
            self._repository,
            name=data.name,
            committee_code=data.committee_code,
            committee_type=data.committee_type,
            department=data.department,
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate committee: {existing.id} ({existing.title!r}) already carries this "
                f"code / name+type+department."
            )

        link_ids: dict[str, list[ObjectId]] = {}
        for group in COMMITTEE_LINK_GROUPS:
            raw_ids = list(getattr(data, group) or [])
            ids = [ObjectId.parse(raw) for raw in raw_ids]
            assert_link_targets(self._repository, group, ids)
            link_ids[group] = ids
        assert_member_persons(self._repository, data.members)

        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(
                    key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                )
            )

        put(KEY_COMMITTEE_CODE, data.committee_code)
        put(KEY_COMMITTEE_TYPE, data.committee_type)
        put(KEY_DEPARTMENT, data.department)
        put(KEY_SCHOOL, data.school)
        put(KEY_DESCRIPTION, data.description)
        put(KEY_CONSTITUTION_DATE, data.constitution_date)
        put(KEY_EXPIRY_DATE, data.expiry_date)
        put(KEY_NOTES, data.notes)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False))
        if data.members:
            put(KEY_MEMBERS, json.dumps(data.members, ensure_ascii=False))

        obj = UniversalObject.create(
            object_type=ObjectType.COMMITTEE,
            title=data.name.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        all_link_ids: list[ObjectId] = []
        for group in COMMITTEE_LINK_GROUPS:
            for target_id in link_ids[group]:
                obj.add_relationship(
                    target_id, RelationshipKind.RELATED_TO, Provenance.ASSERTED,
                    actor=data.created_by.strip(),
                )
                all_link_ids.append(target_id)

        # Member backlinks (faculty/student MEMBER_OF → committee) — the
        # research-team multi-aggregate write precedent.
        member_targets: list[UniversalObject] = []
        for member in data.members:
            person = self._repository.get_by_id(
                ObjectId.parse(str(member["faculty_id"]).strip())
            )
            if person is None:
                continue
            person.add_relationship(
                obj.id, RelationshipKind.MEMBER_OF, Provenance.ASSERTED, actor=data.created_by.strip()
            )
            self._repository.save(person)
            person.pop_domain_events()
            member_targets.append(person)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_link_ids)}
        output = CommitteeOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        enrich_committee_output(self._repository, obj, output)
        return output
