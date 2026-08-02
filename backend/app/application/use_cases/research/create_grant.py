"""Use case: Register a Grant.

Mirrors ``CreateStudentUseCase``: validate -> duplicate check (grant_number,
registry identity, 409) -> L6 metadata record -> asserted edges (FUNDS →
projects, FUNDED_BY → funding agency) -> persist -> events -> output.
"""
from __future__ import annotations

from app.application.commands.create_grant import CreateGrantCommand
from app.application.dtos.research import (
    GRANT_GROUP_TO_KIND,
    KEY_AMOUNT,
    KEY_GRANT_NUMBER,
    KEY_NOTES,
    KEY_RELEASE_SCHEDULE,
    GrantOutput,
    format_amount,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import grant_totals
from app.application.validators.research import assert_valid_create_grant_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

_GROUP_TARGET_TYPES = {
    "projects": (ObjectType.RESEARCH_PROJECT,),
    "funding_agencies": (ObjectType.FUNDING_AGENCY,),
}


def find_grant_duplicates(
    repository: ObjectRepository,
    *,
    grant_number: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: grant_number (case-insensitive, portable)."""
    number = (grant_number or "").strip().casefold()
    if not number:
        return []
    matches: list[UniversalObject] = []
    for grant in repository.find_by_type(ObjectType.GRANT):
        if exclude_id is not None and str(grant.id) == exclude_id:
            continue
        if (grant.metadata.get_value(KEY_GRANT_NUMBER) or "").strip().casefold() == number:
            matches.append(grant)
    return matches


def assert_grant_link_targets(
    repository: ObjectRepository, links: dict[str, tuple[ObjectId, ...]] | None
) -> None:
    for group, ids in (links or {}).items():
        for target_id in ids:
            target = repository.get_by_id(target_id)
            if target_id == ObjectId("") or target is None:
                raise ValidationError(f"Linked object {target_id} not found.")
            if target.object_type not in _GROUP_TARGET_TYPES[group]:
                raise ValidationError(
                    f"links.{group} expects {', '.join(t.value for t in _GROUP_TARGET_TYPES[group])} "
                    f"targets; {target_id} is a {target.object_type.value}."
                )


class CreateGrantUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateGrantCommand) -> GrantOutput:
        data = command.input
        assert_valid_create_grant_input(data)

        duplicates = find_grant_duplicates(self._repository, grant_number=data.grant_number)
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate grant: {existing.id} ({existing.title!r}) already has this "
                f"grant number."
            )

        assert_grant_link_targets(self._repository, data.links)

        entries: list[MetadataEntry] = [
            MetadataEntry(KEY_GRANT_NUMBER, data.grant_number.strip(),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        ]
        for key, value in (
            (KEY_RELEASE_SCHEDULE, data.release_schedule),
            (KEY_NOTES, data.notes),
        ):
            if value is not None and str(value) != "":
                entries.append(
                    MetadataEntry(key, str(value),
                                  MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
                )
        if data.amount is not None:
            entries.append(
                MetadataEntry(KEY_AMOUNT, format_amount(float(data.amount)) or "0",
                              MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        obj = UniversalObject.create(
            object_type=ObjectType.GRANT,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        for group, ids in (data.links or {}).items():
            for target_id in ids:
                obj.add_relationship(
                    target_id, GRANT_GROUP_TO_KIND[group], Provenance.ASSERTED,
                    actor=data.created_by,
                )
        self._repository.save(obj)

        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        all_ids = [oid for ids in (data.links or {}).values() for oid in ids]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        out = GrantOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        out.budget = grant_totals(self._repository, obj)
        return out
