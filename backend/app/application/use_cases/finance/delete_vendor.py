"""Use case: Delete a Vendor.

Mirrors ``DeleteFacultyUseCase`` (plain delete, 404): proposals referencing
the vendor are institutional records on OTHER Objects and survive by design
(the dangling vendor_id is simply skipped on resolution — the frozen
tolerance).
"""
from __future__ import annotations

from app.application.commands.delete_vendor import DeleteVendorCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteVendorUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteVendorCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.VENDOR:
            raise ObjectNotFoundError(f"Vendor {command.object_id} not found.")
        self._repository.delete(command.object_id)
