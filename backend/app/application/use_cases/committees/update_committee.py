"""Use case: Update a Committee — the frozen merge contract.

Mirrors ``UpdateFacultyUseCase`` one-to-one: None = untouched, a provided
value replaces verbatim; tags/members/link groups are group-replaces; a
code/name/type/department change re-runs the registry duplicate scan (409);
member replacement reconciles the MEMBER_OF backlinks on member aggregates
(add the newcomers, remove the departed) — the research-team precedent.
"""
from __future__ import annotations

import json

from app.application.commands.update_committee import UpdateCommitteeCommand
from app.application.dtos.committee import (
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
    committee_edge_group,
)
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.committees.create_committee import (
    assert_link_targets,
    assert_member_persons,
    find_committee_duplicates,
)
from app.application.use_cases.committees.helpers import (
    enrich_committee_output,
    member_rows,
)
from app.application.validators.committee import assert_valid_update_committee_input
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


class UpdateCommitteeUseCase:
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

    def execute(self, command: UpdateCommitteeCommand) -> CommitteeOutput:
        data = command.input
        assert_valid_update_committee_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.COMMITTEE:
            raise ObjectNotFoundError(f"Committee {command.object_id} not found.")

        actor = data.actor.strip()

        if (
            data.committee_code is not None
            or data.name is not None
            or data.committee_type is not None
            or data.department is not None
        ):
            meta = {entry.key: entry.value for entry in obj.metadata.entries}
            duplicates = find_committee_duplicates(
                self._repository,
                name=data.name if data.name is not None else obj.title,
                committee_code=(
                    data.committee_code
                    if data.committee_code is not None
                    else meta.get(KEY_COMMITTEE_CODE)
                ),
                committee_type=(
                    data.committee_type
                    if data.committee_type is not None
                    else meta.get(KEY_COMMITTEE_TYPE)
                ),
                department=(
                    data.department if data.department is not None else meta.get(KEY_DEPARTMENT)
                ),
                exclude_id=str(obj.id),
            )
            if duplicates:
                raise ObjectAlreadyExistsError(
                    f"Duplicate committee: {duplicates[0].id} ({duplicates[0].title!r}) already "
                    f"carries this code / name+type+department."
                )

        if data.name is not None and data.name.strip() != obj.title:
            obj.rename(data.name, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_COMMITTEE_CODE, data.committee_code),
            (KEY_COMMITTEE_TYPE, data.committee_type),
            (KEY_DEPARTMENT, data.department),
            (KEY_SCHOOL, data.school),
            (KEY_DESCRIPTION, data.description),
            (KEY_CONSTITUTION_DATE, data.constitution_date),
            (KEY_EXPIRY_DATE, data.expiry_date),
            (KEY_NOTES, data.notes),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)

        if data.tags is not None:
            self._set(obj, KEY_TAGS, json.dumps(data.tags, ensure_ascii=False), actor)
        if data.members is not None:
            self._replace_members(obj, data.members, actor)

        # PART 7 link groups — group-replaces, same as the faculty module's
        # committees group.
        link_payloads = {
            "projects": data.projects,
            "grants": data.grants,
            "students": data.students,
            "publications": data.publications,
        }
        for group, raw in link_payloads.items():
            if raw is None:
                continue
            new_ids = {ObjectId.parse(item) for item in raw}
            assert_link_targets(self._repository, group, sorted(new_ids, key=str))
            expected_type_group = group
            existing = {
                rel.target: rel
                for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
            }
            # Only reconcile targets that belong to THIS group; other groups'
            # edges stay untouched (group-replace semantics per group).
            for target in list(existing):
                found = self._repository.get_by_id(target)
                if found is None:
                    continue
                if committee_edge_group(
                    RelationshipKind.RELATED_TO, found.object_type
                ) != expected_type_group:
                    continue
                if target not in new_ids:
                    obj.remove_relationship(
                        target, RelationshipKind.RELATED_TO, Provenance.ASSERTED, actor=actor
                    )
            for target in new_ids:
                if target not in existing:
                    obj.add_relationship(
                        target, RelationshipKind.RELATED_TO, Provenance.ASSERTED, actor=actor
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
        output = CommitteeOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        output.links = {
            group: output.links.get(group, []) for group in COMMITTEE_LINK_GROUPS
        }
        enrich_committee_output(self._repository, obj, output)
        return output

    def _replace_members(
        self, obj: UniversalObject, members: list[dict], actor: str
    ) -> None:
        """Reconcile the members JSON + the MEMBER_OF backlinks on member
        aggregates (add newcomers, remove departures)."""
        assert_member_persons(self._repository, members)
        old_ids = {
            str(row.get("faculty_id") or "").strip() for row in member_rows(obj)
        } - {""}
        new_ids = {str(row.get("faculty_id") or "").strip() for row in members} - {""}
        for departed in sorted(old_ids - new_ids):
            person = self._repository.get_by_id(ObjectId.parse(departed))
            if person is not None:
                person.remove_relationship(
                    obj.id, RelationshipKind.MEMBER_OF, Provenance.ASSERTED, actor=actor
                )
                self._repository.save(person)
                person.pop_domain_events()
        for joined in sorted(new_ids - old_ids):
            person = self._repository.get_by_id(ObjectId.parse(joined))
            if person is not None:
                person.add_relationship(
                    obj.id, RelationshipKind.MEMBER_OF, Provenance.ASSERTED, actor=actor
                )
                self._repository.save(person)
                person.pop_domain_events()
        self._set(obj, KEY_MEMBERS, json.dumps(members, ensure_ascii=False), actor)
