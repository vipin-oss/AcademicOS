"""Use case: Fetch one Faculty member — the enriched workspace payload.

Mirrors ``GetProjectUseCase``: type-checked 404, committee links denormalised
in ONE ``find_by_ids`` batch, then the derived lenses (PART 3 research,
PART 4 supervision, PART 5 teaching load, PART 6 dashboard stats) computed
from the frozen relationship graph via the portable repository scans.
"""
from __future__ import annotations

from app.application.dtos.faculty import (
    KEY_LIFECYCLE_STATUS,
    PROJECT_IN_FLIGHT_STATUSES,
    FacultyOutput,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_faculty import GetFacultyQuery
from app.application.use_cases.faculty.helpers import (
    classes_of_faculty,
    grants_of_projects,
    publications_count_of_faculty,
    research_projects_of_faculty,
    supervision_of_faculty,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class GetFacultyUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetFacultyQuery) -> FacultyOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.FACULTY:
            raise ObjectNotFoundError(f"Faculty {query.object_id} not found.")

        faculty_id = str(obj.id)

        # Committee memberships (the edges this module owns) — one batch.
        committee_ids = [rel.target for rel in obj.relationships
                         if rel.kind is RelationshipKind.MEMBER_OF]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(committee_ids)}

        out = FacultyOutput.from_domain(obj, [], linked_by_id=linked_by_id)

        # PART 3 — research integration lens (projects + their grants).
        projects, project_objects = research_projects_of_faculty(self._repository, obj)
        in_flight = 0
        for project in project_objects.values():
            meta = {entry.key: entry.value for entry in project.metadata.entries}
            if (meta.get(KEY_LIFECYCLE_STATUS) or "draft") in PROJECT_IN_FLIGHT_STATUSES:
                in_flight += 1
        grants = grants_of_projects(self._repository, set(project_objects))
        out.research = {"projects": projects, "grants": grants}

        # PART 4 — student supervision (current vs completed).
        out.supervision = supervision_of_faculty(self._repository, faculty_id)

        # PART 5 — teaching load (classes + derived weekly hours).
        classes, total_hours = classes_of_faculty(self._repository, faculty_id)
        out.teaching = {"classes": classes, "total_weekly_hours": total_hours}

        # PART 6 — dashboard cards.
        committee_count = len(out.links.get("committees", []))
        out.stats = {
            "publications": publications_count_of_faculty(self._repository, faculty_id),
            "active_projects": in_flight,
            "grants": len(grants),
            "students_supervised": len(out.supervision["current"]),
            "courses": len(classes),
            "committees": committee_count,
        }
        return out
