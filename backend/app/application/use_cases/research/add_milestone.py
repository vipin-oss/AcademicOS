"""Use case: Add a milestone to a project timeline (PART 8).

A milestone is a ``project_milestone`` Universal Object (BELONGS_TO → the
project) carrying date/status/notes as L6 human-asserted metadata — the
``attendance_session`` precedent. As first-class Objects, milestones feed
the dashboard's upcoming-deadlines panel without any separate store.
"""
from __future__ import annotations

from app.application.commands.add_milestone import AddMilestoneCommand
from app.application.dtos.research import (
    KEY_MILESTONE_DATE,
    KEY_MILESTONE_STATUS,
    KEY_NOTES,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import milestone_output
from app.application.validators.research import assert_valid_milestone_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class AddMilestoneUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: AddMilestoneCommand):
        data = command.input
        assert_valid_milestone_input(data)

        project = self._repository.get_by_id(command.project_id)
        if project is None or project.object_type is not ObjectType.RESEARCH_PROJECT:
            raise ObjectNotFoundError(f"Project {command.project_id} not found.")

        actor = (command.actor or "system").strip() or "system"
        entries: list[MetadataEntry] = [
            MetadataEntry(KEY_MILESTONE_DATE, data.date.strip(),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_MILESTONE_STATUS, data.status,
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        ]
        if data.notes:
            entries.append(
                MetadataEntry(KEY_NOTES, data.notes,
                              MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        milestone = UniversalObject.create(
            object_type=ObjectType.PROJECT_MILESTONE,
            title=data.title.strip(),
            created_by=actor,
            metadata=Metadata(entries=tuple(entries)),
        )
        milestone.add_relationship(
            project.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(milestone)

        events = milestone.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return milestone_output(milestone)
