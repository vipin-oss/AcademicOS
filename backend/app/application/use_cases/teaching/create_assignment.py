"""Use case: Create an Assignment inside a Class (PART D).

Mirrors ``CreateClassUseCase``: validate -> class exists -> L6 human-asserted
metadata record (type, description, instructions, max marks, deadline,
late policy, rubric, visibility, weightage) -> BELONGS_TO edge to the class
-> persist -> events -> output. The assignment IS the reusable academic
object: submissions, marks and Google-Form reimports all anchor to it.
"""
from __future__ import annotations

from app.application.commands.create_assignment import CreateAssignmentCommand
from app.application.dtos.teaching import (
    KEY_ASSIGNMENT_TYPE,
    KEY_DEADLINE,
    KEY_DESCRIPTION,
    KEY_INSTRUCTIONS,
    KEY_LATE_ALLOWED,
    KEY_MAX_MARKS,
    KEY_RUBRIC,
    KEY_VISIBILITY,
    KEY_WEIGHTAGE,
    AssignmentOutput,
    encode_json,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.teaching import assert_valid_create_assignment_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class CreateAssignmentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateAssignmentCommand) -> AssignmentOutput:
        data = command.input
        assert_valid_create_assignment_input(data)

        cls = self._repository.get_by_id(data.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {data.class_id} not found.")

        entries: list[MetadataEntry] = []

        def asserted(key: str, value: str) -> None:
            entries.append(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        asserted(KEY_ASSIGNMENT_TYPE, data.assignment_type)
        asserted(KEY_VISIBILITY, data.visibility)
        asserted(KEY_LATE_ALLOWED, "true" if data.late_allowed else "false")
        for key, value in (
            (KEY_DESCRIPTION, data.description),
            (KEY_INSTRUCTIONS, data.instructions),
            (KEY_DEADLINE, data.deadline),
        ):
            if value is not None and str(value) != "":
                asserted(key, str(value))
        if data.max_marks is not None:
            asserted(KEY_MAX_MARKS, str(data.max_marks))
        if data.weightage is not None:
            asserted(KEY_WEIGHTAGE, str(data.weightage))
        if data.rubric:
            asserted(KEY_RUBRIC, encode_json(list(data.rubric)))

        obj = UniversalObject.create(
            object_type=ObjectType.ASSIGNMENT,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        obj.add_relationship(
            cls.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=data.created_by
        )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return AssignmentOutput.from_domain(obj, events, class_obj=cls)
