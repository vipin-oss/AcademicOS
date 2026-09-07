"""Use case: PART 9 budget tracking — per-project lines.

Approved/released/utilized/remaining per research project, composed from the
frozen research budget helpers plus procurement spend (PAID bills on
proposals linked to each project). Read-only lens: nothing is stored.
"""
from __future__ import annotations

from app.application.dtos.finance import BudgetLine, ListBudgetsResult
from app.application.queries.list_budget_lines import ListBudgetLinesQuery
from app.application.use_cases.finance.helpers import all_proposals, budget_line_for_project
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListBudgetLinesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListBudgetLinesQuery) -> ListBudgetsResult:
        projects = self._repository.find_by_type(
            ObjectType.RESEARCH_PROJECT, owner_user_id=query.owner_user_id
        )
        # Perf hardening (Phase 2/2B audit follow-up): fetch every
        # proposal/grant/installment/expenditure ONCE and share them
        # across every project, instead of each budget_line_for_project()
        # call re-scanning the user's entire PURCHASE table (Phase 2), or
        # the GRANT/GRANT_INSTALLMENT/GRANT_EXPENDITURE tables one level
        # deeper (the N+1 the Phase 2B sweep found nested inside
        # project_budget()).
        proposals = all_proposals(self._repository, owner_user_id=query.owner_user_id)
        grants = self._repository.find_by_type(ObjectType.GRANT, owner_user_id=query.owner_user_id)
        installments = self._repository.find_by_type(
            ObjectType.GRANT_INSTALLMENT, owner_user_id=query.owner_user_id
        )
        expenditures = self._repository.find_by_type(
            ObjectType.GRANT_EXPENDITURE, owner_user_id=query.owner_user_id
        )
        lines = [
            BudgetLine(
                **budget_line_for_project(
                    self._repository, project,
                    owner_user_id=query.owner_user_id, proposals=proposals,
                    grants=grants, installments=installments, expenditures=expenditures,
                )
            )
            for project in projects
        ]
        lines.sort(key=lambda line: (line.title.casefold(), line.project_id))
        return ListBudgetsResult(items=lines)
