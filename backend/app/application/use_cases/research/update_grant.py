"""Use case: Update a Grant (partial — frozen merge contract).

Mirrors ``UpdateStudentUseCase``: None = untouched; grant_number change runs
duplicate detection (409); link groups replace per group (present only).
"""
from __future__ import annotations

from app.application.commands.update_grant import UpdateGrantCommand
from app.application.dtos.research import (
    GRANT_GROUP_TO_KIND,
    KEY_AMOUNT,
    KEY_GRANT_NUMBER,
    KEY_NOTES,
    KEY_RELEASE_SCHEDULE,
    GrantOutput,
    format_amount,
    grant_edge_group,
    linked_target_ids,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.create_grant import (
    assert_grant_link_targets,
    find_grant_duplicates,
)
from app.application.use_cases.research.helpers import (
    expenditure_output,
    expenditures_of_grant,
    grant_totals,
    installment_output,
    installments_of_grant,
)
from app.application.validators.research import assert_valid_update_grant_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateGrantUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def _assert(self, obj: UniversalObject, key: str, value: str, actor: str) -> None:
        if obj.metadata.get_value(key) != value:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

    def execute(self, command: UpdateGrantCommand) -> GrantOutput:
        data = command.input
        assert_valid_update_grant_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.GRANT:
            raise ObjectNotFoundError(f"Grant {command.object_id} not found.")

        actor = data.actor.strip()

        if data.grant_number is not None and (
            data.grant_number.strip().casefold()
            != (obj.metadata.get_value(KEY_GRANT_NUMBER) or "").strip().casefold()
        ):
            dupes = find_grant_duplicates(
                self._repository, grant_number=data.grant_number, exclude_id=str(obj.id)
            )
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Duplicate grant: {dupes[0].id} ({dupes[0].title!r}) already has "
                    f"this grant number."
                )

        if data.links is not None:
            assert_grant_link_targets(self._repository, data.links)
            for group, ids in data.links.items():
                kind = GRANT_GROUP_TO_KIND[group]
                wanted = {str(oid) for oid in ids}
                current = []
                for target in [r.target for r in obj.relationships if r.kind is kind]:
                    linked = self._repository.get_by_id(target)
                    if linked is None or grant_edge_group(kind, linked.object_type) == group:
                        current.append(target)
                for target in current:
                    if str(target) not in wanted:
                        obj.remove_relationship(target, kind, Provenance.ASSERTED, actor=actor)
                present = {str(r.target) for r in obj.relationships if r.kind is kind}
                for oid in ids:
                    if str(oid) not in present:
                        obj.add_relationship(oid, kind, Provenance.ASSERTED, actor=actor)

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        if data.grant_number is not None:
            self._assert(obj, KEY_GRANT_NUMBER, data.grant_number.strip(), actor)
        if data.release_schedule is not None:
            self._assert(obj, KEY_RELEASE_SCHEDULE, data.release_schedule, actor)
        if data.notes is not None:
            self._assert(obj, KEY_NOTES, data.notes, actor)
        if data.amount is not None:
            self._assert(obj, KEY_AMOUNT, format_amount(float(data.amount)) or "0", actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        grant_id = str(obj.id)
        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        out = GrantOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        out.installments = [
            installment_output(i) for i in installments_of_grant(self._repository, grant_id)
        ]
        out.expenditures = [
            expenditure_output(e) for e in expenditures_of_grant(self._repository, grant_id)
        ]
        out.budget = grant_totals(self._repository, obj)
        return out
