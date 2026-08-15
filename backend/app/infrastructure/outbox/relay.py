"""Outbox relay (Sprint-4 Milestone A).

Reads undelivered outbox rows and marks them delivered. The relay is the
durable, replayable seam: a consumer (search S5, assistant S6, timeline)
polls ``pending()``, processes each row, then ``mark_delivered()`` —
idempotently, because the row's ``event_id`` is the aggregate's
``DomainEvent.event_id`` UUID. Until a consumer exists, rows simply stay
pending — they are never lost and never duplicated.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infrastructure.db.models.outbox_model import OutboxEventModel


class OutboxRelay:
    def __init__(self, session: Session) -> None:
        self._session = session

    def pending(self, limit: int = 200) -> list[dict]:
        """Undelivered outbox rows, oldest first (bounded)."""
        rows = self._session.execute(
            select(OutboxEventModel)
            .where(OutboxEventModel.delivered_at.is_(None))
            .order_by(OutboxEventModel.id)
            .limit(limit)
        ).scalars().all()
        return [
            {
                "event_id": row.event_id,
                "aggregate_id": row.aggregate_id,
                "event_type": row.event_type,
                "payload": row.payload,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def mark_delivered(self, event_ids: Sequence[str], *, at: str) -> int:
        """Mark the given events delivered; returns the number marked.

        Idempotent: already-delivered ids are skipped (the WHERE clause
        only matches undelivered rows).
        """
        if not event_ids:
            return 0
        result = self._session.execute(
            update(OutboxEventModel)
            .where(
                OutboxEventModel.event_id.in_(list(event_ids)),
                OutboxEventModel.delivered_at.is_(None),
            )
            .values(delivered_at=at)
        )
        self._session.commit()
        return result.rowcount or 0
