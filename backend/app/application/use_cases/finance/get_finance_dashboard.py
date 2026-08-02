"""Use case: Finance & Procurement dashboard cards (PART 11).

Computed read (the committees dashboard precedent) — no stored counters.
"""
from __future__ import annotations

from app.application.dtos.finance import FinanceDashboard
from app.application.queries.get_finance_dashboard import GetFinanceDashboardQuery
from app.application.use_cases.finance.helpers import finance_dashboard
from app.domain.repositories.object_repository import ObjectRepository


class GetFinanceDashboardUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetFinanceDashboardQuery) -> FinanceDashboard:
        cards = finance_dashboard(self._repository)
        return FinanceDashboard(
            active_procurements=cards["active_procurements"],
            pending_approvals=cards["pending_approvals"],
            total_vendors=cards["total_vendors"],
            total_purchase_orders=cards["total_purchase_orders"],
            budget_utilized=cards["budget_utilized"],
            budget_remaining=cards["budget_remaining"],
            pending_bills=cards["pending_bills"],
        )
