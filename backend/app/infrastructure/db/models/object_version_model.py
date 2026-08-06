"""SQLAlchemy model for the ``object_versions`` snapshot table (Sprint-4 Milestone B).

One immutable row per version an Object has ever stored. When the repository
persists a version it has never recorded before (a create, or a save whose
``version`` actually changed), it appends a row in the SAME transaction as
the object row, holding the frozen ``ObjectSnapshot.to_dict()``
representation. Rows are never updated — a version's state is captured once
and stays exactly what it was.

Design notes:

- ``UNIQUE (object_id, version)`` mirrors the version-keyed immutability
  invariant: the same version of the same object can never be recorded twice.
- ``object_id`` has an ``ON DELETE CASCADE`` foreign key (PostgreSQL); the
  repository deletes version rows explicitly so SQLite behaves identically —
  the same doctrine as the edge table.
- ``snapshot`` is stored with the same JSONB/JSON type doctrine as the
  ``objects`` and ``outbox_events`` tables.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.types import JSONBType


class ObjectVersionModel(Base):
    __tablename__ = "object_versions"
    __table_args__ = (
        UniqueConstraint(
            "object_id", "version", name="uq_object_versions_object_id_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(
        String, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSONB on PostgreSQL; JSON elsewhere (same doctrine as the objects table).
    # Holds the existing ObjectSnapshot.to_dict() representation — no new
    # format was invented for versioning.
    snapshot: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
