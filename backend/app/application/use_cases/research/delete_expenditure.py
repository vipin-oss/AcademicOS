"""Use case: Delete a grant expenditure entry (correction path)."""
from __future__ import annotations

from app.application.commands.delete_expenditure import DeleteExpenditureCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteExpenditureUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteExpenditureCommand) -> None:
        obj = self._repository.get_by_id(command.expenditure_id)
        if obj is None or obj.object_type is not ObjectType.GRANT_EXPENDITURE:
            raise ObjectNotFoundError(f"Expenditure {command.expenditure_id} not found.")
        self._repository.delete(command.expenditure_id)
