"""SQL implementation of the CDM-decision audit store (L3, ADR-032)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.cdm_decision_store import CdmDecisionStore
from app.application.services.decision_records import DecisionRecord
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel


class SQLCdmDecisionStore(CdmDecisionStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: DecisionRecord) -> DecisionRecord:
        existing = self._session.execute(
            select(CdmDecisionModel).where(
                CdmDecisionModel.decision_id == record.decision_id
            )
        ).scalars().first()
        if existing is not None:
            return record
        self._session.add(
            CdmDecisionModel(
                decision_id=record.decision_id,
                subject_id=record.subject_id,
                decision=record.decision,
                reviewer=record.reviewer,
                previous_status=record.previous_status,
                resulting_status=record.resulting_status,
                notes=record.notes,
                acl_scope=record.acl_scope,
                created_at=record.created_at,
            )
        )
        return record

    def by_block(self, block_id: str) -> list[DecisionRecord]:
        rows = self._session.execute(
            select(CdmDecisionModel)
            .where(CdmDecisionModel.subject_id == block_id)
            .order_by(CdmDecisionModel.created_at, CdmDecisionModel.id)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def recent(self, limit: int = 50) -> list[DecisionRecord]:
        rows = self._session.execute(
            select(CdmDecisionModel)
            .order_by(CdmDecisionModel.created_at.desc(), CdmDecisionModel.id.desc())
            .limit(limit)
        ).scalars().all()
        return [_from_model(r) for r in rows]


def _from_model(row: CdmDecisionModel) -> DecisionRecord:
    return DecisionRecord(
        decision_id=row.decision_id,
        subject_id=row.subject_id,
        decision=row.decision,
        reviewer=row.reviewer,
        previous_status=row.previous_status,
        resulting_status=row.resulting_status,
        notes=row.notes,
        acl_scope=row.acl_scope,
        created_at=row.created_at,
    )
