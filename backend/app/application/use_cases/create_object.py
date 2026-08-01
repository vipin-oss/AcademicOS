"""Use case: Create Universal Object.

Vertical slice flow:
  Input DTO -> Validation -> Domain Object creation -> Repository Interface
  -> Domain Events -> Output DTO

Depends only on the abstract ``ObjectRepository`` port (from Domain) and on the
``DomainEventPublisher`` port (defined in this Application layer). No SQLAlchemy,
FastAPI, HTTP, JWT, AI, or infrastructure here.
"""
from __future__ import annotations

from app.application.commands.create_object import CreateObjectCommand
from app.application.dtos.object import CreateObjectOutput
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.object import assert_valid_create_object_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository


class CreateObjectUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateObjectCommand) -> CreateObjectOutput:
        # 1. Validate boundary input
        assert_valid_create_object_input(command.input)

        # 2. Conflict guard via the repository interface (no impl here)
        if (
            command.input.object_id is not None
            and self._repository.exists(command.input.object_id)
        ):
            raise ObjectAlreadyExistsError(
                f"Object {command.input.object_id} already exists."
            )

        # 3. Create the domain aggregate (emits an ObjectCreated domain event)
        obj = UniversalObject.create(
            object_type=command.input.object_type,
            title=command.input.title,
            created_by=command.input.created_by,
            object_id=command.input.object_id,
            status=command.input.status,
            metadata=command.input.metadata,
        )

        # 4. Persist via the abstract repository interface
        self._repository.save(obj)

        # 5. Collect domain events raised by the aggregate
        events = obj.pop_domain_events()

        # 6. Project events through the port (infrastructure-agnostic)
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        # 7. Return the output DTO
        return CreateObjectOutput.from_domain(obj, events)
