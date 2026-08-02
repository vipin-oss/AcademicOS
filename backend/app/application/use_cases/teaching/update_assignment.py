"""Use case: Update an Assignment (partial; frozen merge contract).

Mirrors ``UpdateClassUseCase``: ``None`` = untouched, a provided value
replaces; every mutation via its aggregate method (versioning, audit,
events intact). The owning class (BELONGS_TO edge) is not editable here —
an assignment never silently moves class.
"""
from __future__ import annotations

from app.application.commands.update_assignment import UpdateAssignmentCommand
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
from app.application.use_cases.teaching.helpers import class_id_of_assignment
from app.application.validators.teaching import assert_valid_update_assignment_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class UpdateAssignmentUseCase:
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

    def execute(self, command: UpdateAssignmentCommand) -> AssignmentOutput:
        data = command.input
        assert_valid_update_assignment_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {command.object_id} not found.")

        actor = data.actor.strip()

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        if data.assignment_type is not None:
            self._assert(obj, KEY_ASSIGNMENT_TYPE, data.assignment_type, actor)
        if data.visibility is not None:
            self._assert(obj, KEY_VISIBILITY, data.visibility, actor)
        if data.late_allowed is not None:
            self._assert(obj, KEY_LATE_ALLOWED, "true" if data.late_allowed else "false", actor)
        for key, value in (
            (KEY_DESCRIPTION, data.description),
            (KEY_INSTRUCTIONS, data.instructions),
            (KEY_DEADLINE, data.deadline),
        ):
            if value is not None:
                self._assert(obj, key, str(value), actor)
        if data.max_marks is not None:
            self._assert(obj, KEY_MAX_MARKS, str(data.max_marks), actor)
        if data.weightage is not None:
            self._assert(obj, KEY_WEIGHTAGE, str(data.weightage), actor)
        if data.rubric is not None:
            self._assert(obj, KEY_RUBRIC, encode_json(list(data.rubric)), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        class_id = class_id_of_assignment(obj)
        class_obj = (
            self._repository.get_by_id(ObjectId(class_id)) if class_id is not None else None
        )
        return AssignmentOutput.from_domain(obj, events, class_obj=class_obj)
