"""Entity match decision database model.

Stores professor decisions about entity matches with full provenance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Text

from app.infrastructure.db.models.object_model import Base


class EntityMatchModel(Base):
    """Persistent record of an entity match decision."""

    __tablename__ = "entity_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_doc_id = Column(String(255), nullable=False, index=True)
    target_doc_id = Column(String(255), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    evidence = Column(Text, nullable=False)  # JSON string
    decision = Column(String(20), nullable=False, default="pending", index=True)
    decided_by = Column(String(255), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_doc_id": self.source_doc_id,
            "target_doc_id": self.target_doc_id,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
