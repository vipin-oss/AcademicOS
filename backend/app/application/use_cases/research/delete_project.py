"""Use case: Delete a Research Project.

Mirrors ``DeleteStudentUseCase``. Grants, publications, documents and team
members are institutional records on OTHER Objects and survive by design
(the FUNDS/FUNDED_BY/LEADS/… edges simply dangle and are skipped on
denormalisation — the frozen tolerance). Milestone children exist only as
the project's plan and are deleted with it (documented cascade), so the
dashboard's upcoming-deadlines panel never leaks orphans.
"""
from __future__ import annotations

from app.application.commands.delete_project import DeleteProjectCommand
from app.application.exceptions import ObjectNotFoundError
from app.application.use_cases.research.helpers import milestones_of_project
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class DeleteProjectUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteProjectCommand) -> None:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.RESEARCH_PROJECT:
            raise ObjectNotFoundError(f"Project {command.object_id} not found.")
        project_id = str(obj.id)
        for milestone in milestones_of_project(self._repository, project_id):
            self._repository.delete(milestone.id)
        self._repository.delete(command.object_id)
