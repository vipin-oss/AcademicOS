"""Use case: Update a Universal Object.

Applies only the mutations the frozen Domain aggregate supports: status changes
(via ``change_status``) and metadata changes (via ``set_metadata``). Title is not
mutated — the Domain has no title-setter and the Domain is frozen. The object is
re-persisted through the existing ``save`` (upsert) repository method, so no new
repository method is introduced.
"""
from __future__ import annotations

from app.application.commands.update_object import UpdateObjectCommand
from app.application.dtos.object import CreateObjectOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.object import assert_valid_update_object_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository


class UpdateObjectUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UpdateObjectCommand) -> CreateObjectOutput:
        assert_valid_update_object_input(command.input)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object {command.object_id} not found.")

        if command.input.status is not None and command.input.status != obj.status:
            obj.change_status(command.input.status, command.input.updated_by)

        if command.input.metadata is not None:
            for entry in command.input.metadata.entries:
                obj.set_metadata(entry, actor=command.input.updated_by)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        return CreateObjectOutput.from_domain(obj, events)
