"""SQL adapter for the entity match store port."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.application.ports.entity_match_store import (
    EntityMatchRecord,
    EntityMatchStore,
    MatchDecision,
)
from app.infrastructure.db.models.entity_match_model import EntityMatchModel


def _to_record(model: EntityMatchModel) -> EntityMatchRecord:
    """Convert ORM model to domain record."""
    return EntityMatchRecord(
        id=model.id,
        source_doc_id=model.source_doc_id,
        target_doc_id=model.target_doc_id,
        confidence=model.confidence,
        evidence=model.evidence,
        decision=MatchDecision(model.decision),
        decided_by=model.decided_by,
        decided_at=model.decided_at,
        created_at=model.created_at,
    )


class SQLEntityMatchStore(EntityMatchStore):
    """SQLAlchemy-backed entity match store."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def put(
        self,
        source_doc_id: str,
        target_doc_id: str,
        confidence: float,
        evidence: str,
        decision: MatchDecision = MatchDecision.PENDING,
        decided_by: Optional[str] = None,
    ) -> EntityMatchRecord:
        """Create or update a match decision. Idempotent by (source, target)."""
        # Check for existing record
        existing = (
            self._db.query(EntityMatchModel)
            .filter(
                EntityMatchModel.source_doc_id == source_doc_id,
                EntityMatchModel.target_doc_id == target_doc_id,
            )
            .first()
        )

        if existing is not None:
            # Update if decision changed
            if existing.decision != decision.value:
                existing.decision = decision.value
                existing.decided_by = decided_by
                existing.decided_at = datetime.now(timezone.utc) if decided_by else None
                self._db.flush()
            return _to_record(existing)

        # Create new record
        model = EntityMatchModel(
            source_doc_id=source_doc_id,
            target_doc_id=target_doc_id,
            confidence=confidence,
            evidence=evidence,
            decision=decision.value,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc) if decided_by else None,
        )
        self._db.add(model)
        self._db.flush()
        return _to_record(model)

    def get(self, source_doc_id: str, target_doc_id: str) -> Optional[EntityMatchRecord]:
        """Get a specific match decision."""
        model = (
            self._db.query(EntityMatchModel)
            .filter(
                EntityMatchModel.source_doc_id == source_doc_id,
                EntityMatchModel.target_doc_id == target_doc_id,
            )
            .first()
        )
        return _to_record(model) if model else None

    def by_source(self, source_doc_id: str) -> list[EntityMatchRecord]:
        """Get all matches for a source document."""
        models = (
            self._db.query(EntityMatchModel)
            .filter(EntityMatchModel.source_doc_id == source_doc_id)
            .order_by(EntityMatchModel.created_at.desc())
            .all()
        )
        return [_to_record(m) for m in models]

    def pending_for_user(self, user_id: str) -> list[EntityMatchRecord]:
        """Get all pending matches for documents owned by a user.

        This requires joining with the object table to check ownership,
        but for simplicity we return all pending matches (ACL checked at API level).
        """
        models = (
            self._db.query(EntityMatchModel)
            .filter(EntityMatchModel.decision == MatchDecision.PENDING.value)
            .order_by(EntityMatchModel.created_at.desc())
            .all()
        )
        return [_to_record(m) for m in models]

    def update_decision(
        self,
        source_doc_id: str,
        target_doc_id: str,
        decision: MatchDecision,
        decided_by: str,
    ) -> Optional[EntityMatchRecord]:
        """Update the decision for a match. Returns None if not found."""
        model = (
            self._db.query(EntityMatchModel)
            .filter(
                EntityMatchModel.source_doc_id == source_doc_id,
                EntityMatchModel.target_doc_id == target_doc_id,
            )
            .first()
        )
        if model is None:
            return None

        model.decision = decision.value
        model.decided_by = decided_by
        model.decided_at = datetime.now(timezone.utc)
        self._db.flush()
        return _to_record(model)
