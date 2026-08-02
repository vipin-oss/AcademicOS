"""Use case: Delete a grant installment (correction path)."""
from __future__ import annotations

from app.application.commands.delete_installment import DeleteInstallmentCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteInstallmentUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteInstallmentCommand) -> None:
        obj = self._repository.get_by_id(command.installment_id)
        if obj is None or obj.object_type is not ObjectType.GRANT_INSTALLMENT:
            raise ObjectNotFoundError(f"Installment {command.installment_id} not found.")
        self._repository.delete(command.installment_id)
