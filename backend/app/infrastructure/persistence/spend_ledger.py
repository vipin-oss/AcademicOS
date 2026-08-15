"""SQL implementation of the AI spend ledger (V3 M12, ADR-059)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.ports.spend_ledger import SpendLedger, SpendRecord
from app.infrastructure.db.models.spend_ledger_model import SpendLedgerModel


class SQLSpendLedger(SpendLedger):
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, spend: SpendRecord) -> SpendRecord:
        existing = self._session.execute(
            select(SpendLedgerModel).where(SpendLedgerModel.id == spend.id)
        ).scalars().first()
        if existing is not None:
            return spend  # idempotent
        self._session.add(
            SpendLedgerModel(
                id=spend.id,
                tenant_id=spend.tenant_id,
                owner_user_id=spend.user_id,
                user_id=spend.user_id,
                provider_id=spend.provider_id,
                model=spend.model,
                input_tokens=spend.input_tokens,
                output_tokens=spend.output_tokens,
                estimated_cost_usd=spend.estimated_cost_usd,
                created_at=spend.created_at,
            )
        )
        return spend

    def total_for_user(self, user_id: str) -> float:
        total = self._session.execute(
            select(func.coalesce(func.sum(SpendLedgerModel.estimated_cost_usd), 0.0)).where(
                SpendLedgerModel.user_id == user_id
            )
        ).scalar()
        return float(total or 0.0)

    def total_for_tenant(self, tenant_id: str) -> float:
        total = self._session.execute(
            select(func.coalesce(func.sum(SpendLedgerModel.estimated_cost_usd), 0.0)).where(
                SpendLedgerModel.tenant_id == tenant_id
            )
        ).scalar()
        return float(total or 0.0)
