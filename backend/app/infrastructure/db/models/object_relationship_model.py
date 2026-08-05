"""SQLAlchemy model for the ``object_relationships`` edge table.

R1 — Object Graph physical model. Graph edges are first-class physical rows:
typed, directed, attributed records owned by their source Object.

Design notes:

- The ``UNIQUE`` constraint on ``(source_id, target_id, kind, provenance)``
  mirrors the domain's ``Relationship.identity`` de-duplication key, so the
  physical layer enforces exactly the invariant the aggregate enforces.
- ``target_id`` deliberately has **no** foreign key: the domain permits a
  relationship whose target Object does not exist yet (deferred edges), so a
  strict FK would reject legitimate writes. Integrity from the source side is
  guaranteed by ``ON DELETE CASCADE`` (PostgreSQL) plus explicit edge deletion
  in the repository, so SQLite behaves identically.
- ``created_at`` is stored as the ISO-8601 string produced by the snapshot
  layer so the Domain <-> Snapshot <-> storage round-trip is lossless and the
  frozen ``SnapshotMapper`` contract is untouched. ISO-8601 UTC strings sort
  chronologically, so ``ORDER BY id`` (insertion order) preserves the
  aggregate's relationship list order on read.
"""
from __future__ import annotations

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.types import JSONBType


class ObjectRelationshipModel(Base):
    __tablename__ = "object_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "kind", "provenance",
            name="uq_object_relationships_identity",
        ),
        # Inbound traversal: every edge pointing at an Object.
        Index("ix_object_relationships_target_id", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
