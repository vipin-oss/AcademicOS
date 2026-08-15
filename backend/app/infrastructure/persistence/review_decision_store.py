"""SQLAlchemy adapter for the ``ReviewDecisionStore`` port (Sprint-7 M5).

The single writer of the ``review_decisions`` table, shaped like the
``SQLEvalRunStore``: a thin ``Session`` wrapper that maps ``ReviewDecision``
records to rows and back, one commit per appended decision (a recorded
decision is durable the moment ``add`` returns; a crash before the commit
simply means the action was never logged — the reviewer re-submits and a
new decision row is appended, so the audit trail stays complete).

Row mapping is the only place that touches the table.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.review_decision_store import ReviewDecisionStore
from app.application.services.assistant_review import ReviewDecision
from app.infrastructure.db.models.review_decision_model import ReviewDecisionModel


class SQLReviewDecisionStore(ReviewDecisionStore):
    """Persists ``ReviewDecision`` records to the ``review_decisions`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------- writes
    def add(self, decision: ReviewDecision) -> ReviewDecision:
        self._session.add(
            ReviewDecisionModel(
                decision_id=decision.decision_id,
                conversation_id=decision.conversation_id,
                decision=decision.decision,
                reviewer=decision.reviewer,
                previous_status=decision.previous_status,
                notes=decision.notes,
                rating=decision.rating,
                confidence=decision.confidence,
                eval_run_id=decision.eval_run_id,
                created_at=decision.created_at,
            )
        )
        self._session.commit()
        return decision

    # -------------------------------------------------------------- reads
    def by_conversation(self, conversation_id: str) -> list[ReviewDecision]:
        rows = (
            self._session.execute(
                select(ReviewDecisionModel)
                .where(ReviewDecisionModel.conversation_id == conversation_id)
                .order_by(ReviewDecisionModel.created_at.asc(), ReviewDecisionModel.id.asc())
            )
            .scalars()
            .all()
        )
        return [self._from_row(row) for row in rows]

    def recent(self, limit: int) -> list[ReviewDecision]:
        rows = (
            self._session.execute(
                select(ReviewDecisionModel)
                .order_by(ReviewDecisionModel.created_at.desc(), ReviewDecisionModel.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [self._from_row(row) for row in rows]

    # ------------------------------------------------------------- mapping
    @staticmethod
    def _from_row(row: ReviewDecisionModel) -> ReviewDecision:
        return ReviewDecision(
            decision_id=row.decision_id,
            conversation_id=row.conversation_id,
            decision=row.decision,
            reviewer=row.reviewer,
            previous_status=row.previous_status,
            notes=row.notes,
            rating=row.rating,
            confidence=row.confidence,
            eval_run_id=row.eval_run_id,
            created_at=row.created_at,
        )


__all__ = ["SQLReviewDecisionStore"]
