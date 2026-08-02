"""Use case: Delete a Grant.

Mirrors ``DeleteStudentUseCase``. The grant's installment/expenditure
children are deleted with it (documented cascade — they have no meaning
outside the grant); project/agency Objects and their edges live on.
"""
from __future__ import annotations

from app.application.commands.delete_grant import DeleteGrantCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.use_cases.research.helpers import (
    expenditures_of_grant,
    installments_of_grant,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteGrantUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteGrantCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.GRANT:
            raise ObjectNotFoundError(f"Grant {command.object_id} not found.")
        grant_id = str(obj.id)
        for child in installments_of_grant(self._repository, grant_id):
            self._repository.delete(child.id)
        for child in expenditures_of_grant(self._repository, grant_id):
            self._repository.delete(child.id)
        self._repository.delete(command.object_id)
