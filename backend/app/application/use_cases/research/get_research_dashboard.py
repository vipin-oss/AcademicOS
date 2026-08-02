"""Use case: Research dashboard (PART 10).

Computed view — one source of truth (the Project/Grant/Milestone Objects),
mirroring ``get_teaching_dashboard``:

  cards           total / in-flight (approved+funded+active) / completed
                  projects, total grants, Σ budget_approved, Σ budget_utilized
                  (project-level MVP tracking — no accounting system)
  upcoming        pending/in-progress milestones across every project,
                  date order (overdue first), each carrying its project title
"""
from __future__ import annotations

from app.application.dtos.research import (
    KEY_BUDGET_APPROVED,
    KEY_BUDGET_UTILIZED,
    KEY_LIFECYCLE_STATUS,
    KEY_MILESTONE_DATE,
    PROJECT_IN_FLIGHT_STATUSES,
    ResearchDashboardOutput,
    UpcomingDeadline,
    parse_amount,
)
from app.application.queries.get_research_dashboard import GetResearchDashboardQuery
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetResearchDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetResearchDashboardQuery) -> ResearchDashboardOutput:
        projects = self._repository.find_by_type(ObjectType.RESEARCH_PROJECT)

        def lifecycle(obj) -> str:
            return obj.metadata.get_value(KEY_LIFECYCLE_STATUS) or "draft"

        in_flight = sum(1 for p in projects if lifecycle(p) in PROJECT_IN_FLIGHT_STATUSES)
        completed = sum(1 for p in projects if lifecycle(p) == "completed")
        approved = sum(
            parse_amount(p.metadata.get_value(KEY_BUDGET_APPROVED)) or 0.0 for p in projects
        )
        utilized = sum(
            parse_amount(p.metadata.get_value(KEY_BUDGET_UTILIZED)) or 0.0 for p in projects
        )

        grants = self._repository.find_by_type(ObjectType.GRANT)

        project_titles = {str(p.id): p.title for p in projects}
        deadlines: list[UpcomingDeadline] = []
        for milestone in self._repository.find_by_type(ObjectType.PROJECT_MILESTONE):
            status = milestone.metadata.get_value("milestone_status") or "pending"
            if status == "done":
                continue
            project_id = next(
                (str(rel.target) for rel in milestone.relationships
                 if rel.kind.value == "belongs_to"),
                None,
            )
            if project_id is None or project_id not in project_titles:
                continue  # orphan tolerance (frozen doctrine)
            deadlines.append(
                UpcomingDeadline(
                    milestone_id=str(milestone.id),
                    title=milestone.title,
                    date=milestone.metadata.get_value(KEY_MILESTONE_DATE),
                    status=status,
                    project_id=project_id,
                    project_title=project_titles[project_id],
                )
            )
        deadlines.sort(key=lambda d: (d.date or "￿", d.project_title.casefold(), d.title.casefold()))

        limit = max(1, min(int(query.upcoming_limit or 10), 50))
        return ResearchDashboardOutput(
            total_projects=len(projects),
            active_projects=in_flight,
            completed_projects=completed,
            total_grants=len(grants),
            budget_approved=round(approved, 2),
            budget_utilized=round(utilized, 2),
            upcoming_deadlines=deadlines[:limit],
        )
