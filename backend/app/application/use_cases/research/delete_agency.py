"""Use case: Delete a Funding Agency.

Mirrors ``DeleteStudentUseCase``: grants/projects that cite the agency keep
their (now dangling) FUNDED_BY edge, skipped on denormalisation — the frozen
tolerance; the agency's grants are never deleted implicitly.
"""
from __future__ import annotations

from app.application.commands.delete_agency import DeleteAgencyCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteAgencyUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteAgencyCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.FUNDING_AGENCY:
            raise ObjectNotFoundError(f"Funding agency {command.object_id} not found.")
        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
