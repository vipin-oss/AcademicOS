"""Use case: Update a project milestone (partial — title/date/status/notes)."""
from __future__ import annotations

from app.application.commands.update_milestone import UpdateMilestoneCommand
from app.application.dtos.research import (
    KEY_MILESTONE_DATE,
    KEY_MILESTONE_STATUS,
    KEY_NOTES,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import milestone_output
from app.application.validators.research import assert_valid_update_milestone_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateMilestoneUseCase:
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

    def execute(self, command: UpdateMilestoneCommand):
        data = command.input
        assert_valid_update_milestone_input(data)

        milestone = self._repository.get_by_id(command.milestone_id)
        if milestone is None or milestone.object_type is not ObjectType.PROJECT_MILESTONE:
            raise ObjectNotFoundError(f"Milestone {command.milestone_id} not found.")

        actor = data.actor.strip()
        if data.title is not None and data.title.strip() != milestone.title:
            milestone.rename(data.title, actor)
        if data.date is not None:
            self._assert(milestone, KEY_MILESTONE_DATE, data.date.strip(), actor)
        if data.status is not None:
            self._assert(milestone, KEY_MILESTONE_STATUS, data.status, actor)
        if data.notes is not None:
            self._assert(milestone, KEY_NOTES, data.notes, actor)

        self._repository.save(milestone)
        events = milestone.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return milestone_output(milestone)
