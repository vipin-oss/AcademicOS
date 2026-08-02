"""Use case: Update an action item — the frozen merge contract (PART 5)."""
from __future__ import annotations

from app.application.commands.update_action_item import UpdateActionItemCommand
from app.application.dtos.committee import (
    KEY_ACTION_STATUS,
    KEY_ASSIGNED_NAME,
    KEY_ASSIGNED_TO,
    KEY_COMPLETION_DATE,
    KEY_DUE_DATE,
    KEY_PRIORITY,
    KEY_PROGRESS,
    KEY_REMARKS,
    ActionItemOutput,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.committees.add_action_item import resolve_assignee
from app.application.use_cases.committees.helpers import action_item_output
from app.application.validators.committee import assert_valid_update_action_item_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateActionItemUseCase:
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

    def execute(self, command: UpdateActionItemCommand) -> ActionItemOutput:
        data = command.input
        assert_valid_update_action_item_input(data)

        obj = self._repository.get_by_id(command.action_id)
        if obj is None or obj.object_type is not ObjectType.TASK:
            raise ObjectNotFoundError(f"Action item {command.action_id} not found.")

        actor = data.actor.strip()

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.assigned_to is not None:
            assigned_to, assigned_name = resolve_assignee(self._repository, data.assigned_to)
            self._set(obj, KEY_ASSIGNED_TO, assigned_to or "", actor)
            self._set(obj, KEY_ASSIGNED_NAME, assigned_name or "", actor)
        if data.due_date is not None:
            self._set(obj, KEY_DUE_DATE, str(data.due_date), actor)
        if data.priority is not None:
            self._set(obj, KEY_PRIORITY, data.priority.strip().lower(), actor)
        if data.status is not None:
            self._set(obj, KEY_ACTION_STATUS, data.status.strip().lower(), actor)
        if data.progress is not None:
            self._set(obj, KEY_PROGRESS, str(max(0, min(int(data.progress), 100))), actor)
        if data.completion_date is not None:
            self._set(obj, KEY_COMPLETION_DATE, str(data.completion_date), actor)
        if data.remarks is not None:
            self._set(obj, KEY_REMARKS, str(data.remarks), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return action_item_output(obj)
