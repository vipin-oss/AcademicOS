"""Use case: List Research Projects (paginated, PART 9 filters).

Mirrors ``ListStudentsUseCase``: filters evaluated in Python over repository
results (frozen interface), deterministic registry ordering, ONE
``find_by_ids`` batch for link denormalisation on the page slice (no N+1).

PART 9 filters: ``q`` (title/code/objectives/abstract/keywords/grant ref),
``pi`` (PI/team member names — reverse team scan), ``agency`` (linked agency
names), ``status`` (lifecycle), ``year`` (start year), ``department``; plus
the ``object_id`` lens (projects linked to that Object).
"""
from __future__ import annotations

from app.application.dtos.research import (
    ListProjectsResult,
    ProjectOutput,
    linked_target_ids,
)
from app.application.queries.list_projects import ListProjectsQuery
from app.application.use_cases.research.helpers import team_names_of_project
from app.application.validators.research import assert_valid_list_projects_query
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _agency_names(repository: ObjectRepository, obj: UniversalObject) -> str:
    """Linked agency titles for the agency filter haystack."""
    names: list[str] = []
    for target in repository.find_by_ids(
        [rel.target for rel in obj.relationships if rel.kind is RelationshipKind.FUNDED_BY]
    ):
        if target.object_type is ObjectType.FUNDING_AGENCY:
            names.append(target.title)
    return " ".join(names)


def _searchable_text(out: ProjectOutput, agency_names: str, team_names: str) -> str:
    return " ".join(
        [
            out.title,
            out.project_code or "",
            out.grant_number or "",
            out.department or "",
            out.objectives or "",
            out.abstract or "",
            " ".join(out.keywords),
            " ".join(out.tags),
            agency_names,
            team_names,
        ]
    ).casefold()


class ListProjectsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListProjectsQuery) -> ListProjectsResult:
        assert_valid_list_projects_query(query)

        projects = self._repository.find_by_type(ObjectType.RESEARCH_PROJECT)

        if query.object_id is not None:
            target = str(query.object_id)
            projects = [
                project
                for project in projects
                if target in {str(oid) for oid in linked_target_ids(project)}
                # team students' WORKS_IN edges also surface via the students lens;
                # the project lens itself matches outgoing project edges only.
            ]

        rows: list[tuple[ProjectOutput, UniversalObject, str, str]] = []
        for project in projects:
            out = ProjectOutput.from_domain(project, [])
            agency_names = ""
            team_names = ""
            if (query.q and query.q.strip()) or (query.agency and query.agency.strip()):
                agency_names = _agency_names(self._repository, project)
            if (query.q and query.q.strip()) or (query.pi and query.pi.strip()):
                team_names = team_names_of_project(self._repository, str(project.id))
            rows.append((out, project, agency_names, team_names))

        def matches(row: tuple[ProjectOutput, UniversalObject, str, str]) -> bool:
            out, _project, agency_names, team_names = row
            if query.status and out.lifecycle_status != query.status:
                return False
            if query.department and (out.department or "").casefold() != query.department.casefold():
                return False
            if query.year is not None:
                if not (out.start_date or "").startswith(str(query.year)):
                    return False
            if query.agency and query.agency.strip():
                if query.agency.strip().casefold() not in agency_names.casefold():
                    return False
            if query.pi and query.pi.strip():
                if query.pi.strip().casefold() not in team_names.casefold():
                    return False
            if query.q and query.q.strip():
                haystack = _searchable_text(out, agency_names, team_names)
                tokens = [t for t in query.q.casefold().split() if t]
                if not all(token in haystack for token in tokens):
                    return False
            return True

        rows = [row for row in rows if matches(row)]
        total_count = len(rows)

        # Default ordering: title, then id (registry reading order; stable,
        # deterministic like the other registries).
        rows.sort(key=lambda row: (row[0].title.casefold(), row[0].id))
        start = (query.page - 1) * query.page_size
        page_rows = rows[start:start + query.page_size]

        # Batch-resolve linked objects for the page slice only (no N+1).
        all_ids = []
        for _out, project, _a, _t in page_rows:
            all_ids.extend(linked_target_ids(project))
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        items = [
            ProjectOutput.from_domain(project, [], linked_by_id=linked_by_id)
            for _out, project, _a, _t in page_rows
        ]

        return ListProjectsResult(
            items=items, total_count=total_count, page=query.page, page_size=query.page_size
        )
