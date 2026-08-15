"""SQL implementation of the claim-decision audit store (L3, ADR-032)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.claim_decision_store import ClaimDecisionStore
from app.application.services.decision_records import DecisionRecord
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel


class SQLClaimDecisionStore(ClaimDecisionStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: DecisionRecord) -> DecisionRecord:
        existing = self._session.execute(
            select(ClaimDecisionModel).where(
                ClaimDecisionModel.decision_id == record.decision_id
            )
        ).scalars().first()
        if existing is not None:
            return record  # idempotent: duplicate decision is a no-op
        self._session.add(
            ClaimDecisionModel(
                decision_id=record.decision_id,
                subject_id=record.subject_id,
                decision=record.decision,
                reviewer=record.reviewer,
                previous_status=record.previous_status,
                resulting_status=record.resulting_status,
                notes=record.notes,
                acl_scope=record.acl_scope,
                eval_run_id=record.eval_run_id,
                created_at=record.created_at,
            )
        )
        return record

    def by_claim(self, claim_id: str) -> list[DecisionRecord]:
        rows = self._session.execute(
            select(ClaimDecisionModel)
            .where(ClaimDecisionModel.subject_id == claim_id)
            .order_by(ClaimDecisionModel.created_at, ClaimDecisionModel.id)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def recent(self, limit: int = 50) -> list[DecisionRecord]:
        rows = self._session.execute(
            select(ClaimDecisionModel)
            .order_by(ClaimDecisionModel.created_at.desc(), ClaimDecisionModel.id.desc())
            .limit(limit)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def recent_corrections(self, limit: int = 200) -> list[DecisionRecord]:
        rows = self._session.execute(
            select(ClaimDecisionModel)
            .where(ClaimDecisionModel.decision == "correct")
            .order_by(ClaimDecisionModel.created_at.desc(), ClaimDecisionModel.id.desc())
            .limit(limit)
        ).scalars().all()
        return [_from_model(r) for r in rows]


def _from_model(row: ClaimDecisionModel) -> DecisionRecord:
    return DecisionRecord(
        decision_id=row.decision_id,
        subject_id=row.subject_id,
        decision=row.decision,
        reviewer=row.reviewer,
        previous_status=row.previous_status,
        resulting_status=row.resulting_status,
        notes=row.notes,
        acl_scope=row.acl_scope,
        eval_run_id=row.eval_run_id,
        created_at=row.created_at,
    )
