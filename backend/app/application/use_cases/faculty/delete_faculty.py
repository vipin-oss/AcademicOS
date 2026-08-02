"""Use case: Delete a Faculty member.

Mirrors ``DeleteAgencyUseCase``: a plain delete — the faculty Object owns no
child aggregates. Publications, students, classes, projects and committees
are kept; their edges to the removed id become inert (dangling-edge
tolerance, the established agency precedent).
"""
from __future__ import annotations

from app.application.commands.delete_faculty import DeleteFacultyCommand
from app.application.exceptions import ObjectNotFoundError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteFacultyUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteFacultyCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.FACULTY:
            raise ObjectNotFoundError(f"Faculty {command.object_id} not found.")
        self._repository.delete(command.object_id)
