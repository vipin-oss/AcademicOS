"""Use case: Reports Dashboard (PART 1).

Eleven headline cards — eight module totals + the budget triplet. Everything
is a computed read: counts come from one snapshot scan, the budget triplet
reuses the frozen finance composition (``budget_line_for_project`` — research
budgets + procurement paid-bill spend, PART 7 of Finance) summed over every
research project. No counters are stored anywhere.
"""
from __future__ import annotations

from app.application.dtos.reports import ReportsDashboard
from app.application.queries.get_reports_dashboard import GetReportsDashboardQuery
from app.application.use_cases.finance.helpers import budget_line_for_project
from app.application.use_cases.reports.helpers import Snapshot
from app.domain.repositories.object_repository import ObjectRepository


def reports_dashboard(repository: ObjectRepository) -> ReportsDashboard:
    """Shared builder (the ``events_dashboard`` precedent) — the route's use
    case and the tests both consume this one composition."""
    snapshot = Snapshot(repository)
    approved = utilized = remaining = 0.0
    seen = False
    for project in snapshot["projects"]:
        line = budget_line_for_project(repository, project)
        if line["approved"] is None and line["utilized"] is None:
            continue
        seen = True
        approved += line["approved"] or 0.0
        utilized += line["utilized"] or 0.0
        remaining += line["remaining"] if line["remaining"] is not None else 0.0
    if not seen:
        approved = utilized = remaining = 0.0
    return ReportsDashboard(
        total_publications=len(snapshot["publications"]),
        total_projects=len(snapshot["projects"]),
        total_grants=len(snapshot["grants"]),
        total_students=len(snapshot["students"]),
        total_classes=len(snapshot["classes"]),
        total_faculty=len(snapshot["faculty"]),
        total_committees=len(snapshot["committees"]),
        total_events=len(snapshot["events"]),
        budget_approved=round(approved, 2),
        budget_utilized=round(utilized, 2),
        budget_remaining=round(remaining, 2),
    )


class GetReportsDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetReportsDashboardQuery) -> ReportsDashboard:
        return reports_dashboard(self._repository)
