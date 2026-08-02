"""Use case: Read one Research Project (enriched workspace payload).

Mirrors ``GetStudentUseCase`` + the class workspace: registry fields, link
groups (agencies/committees), reverse-scanned team (PI/Co-PI/members),
milestones (date order), progress update log and the MVP budget — one read
feeds the whole project workspace page.
"""
from __future__ import annotations

from app.application.dtos.research import ProjectOutput, linked_target_ids
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_project import GetProjectQuery
from app.application.use_cases.research.helpers import (
    deflated_team,
    milestone_output,
    milestones_of_project,
    project_budget,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetProjectUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetProjectQuery) -> ProjectOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.RESEARCH_PROJECT:
            raise ObjectNotFoundError(f"Project {query.object_id} not found.")

        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        out = ProjectOutput.from_domain(obj, [], linked_by_id=linked_by_id)
        project_id = str(obj.id)
        out.team = deflated_team(self._repository, project_id)
        out.milestones = [
            milestone_output(m) for m in milestones_of_project(self._repository, project_id)
        ]
        out.budget = project_budget(self._repository, obj)
        return out
