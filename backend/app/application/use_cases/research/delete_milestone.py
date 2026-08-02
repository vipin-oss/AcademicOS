"""Use case: Delete a project milestone."""
from __future__ import annotations

from app.application.commands.delete_milestone import DeleteMilestoneCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteMilestoneUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteMilestoneCommand) -> None:
        milestone = self._repository.get_by_id(command.milestone_id)
        if milestone is None or milestone.object_type is not ObjectType.PROJECT_MILESTONE:
            raise ObjectNotFoundError(f"Milestone {command.milestone_id} not found.")
        self._repository.delete(command.milestone_id)
