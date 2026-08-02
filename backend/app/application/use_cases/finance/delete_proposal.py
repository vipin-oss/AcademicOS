"""Use case: Delete a Purchase Proposal.

Mirrors ``DeleteFacultyUseCase`` (plain delete, 404): the proposal's section
rows ride as its own metadata so nothing cascades; linked projects/grants/
committees/vendors/documents are institutional records on OTHER Objects and
survive by design (the frozen dangling-edge tolerance).
"""
from __future__ import annotations

from app.application.commands.delete_proposal import DeleteProposalCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteProposalUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteProposalCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.PURCHASE:
            raise ObjectNotFoundError(f"Purchase proposal {command.object_id} not found.")
        self._repository.delete(command.object_id)
