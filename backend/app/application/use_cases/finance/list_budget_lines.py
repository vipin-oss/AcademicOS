"""Use case: PART 9 budget tracking — per-project lines.

Approved/released/utilized/remaining per research project, composed from the
frozen research budget helpers plus procurement spend (PAID bills on
proposals linked to each project). Read-only lens: nothing is stored.
"""
from __future__ import annotations

from app.application.dtos.finance import BudgetLine, ListBudgetsResult
from app.application.queries.list_budget_lines import ListBudgetLinesQuery
from app.application.use_cases.finance.helpers import budget_line_for_project
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListBudgetLinesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListBudgetLinesQuery) -> ListBudgetsResult:
        projects = self._repository.find_by_type(ObjectType.RESEARCH_PROJECT)
        lines = [
            BudgetLine(**budget_line_for_project(self._repository, project))
            for project in projects
        ]
        lines.sort(key=lambda line: (line.title.casefold(), line.project_id))
        return ListBudgetsResult(items=lines)
