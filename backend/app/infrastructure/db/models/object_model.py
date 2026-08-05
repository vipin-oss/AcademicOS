"""SQLAlchemy model for the single ``objects`` table.

One table, one row per Universal Object. Structured columns (id, type, title,
status, version) are scalar; the rich, schema-less parts (metadata, audit) are
stored as JSONB on PostgreSQL (and as JSON on other engines via ``JSONBType``).
Graph edges live in ``object_relationships`` (see ``object_relationship_model``)
— R1 Object Graph physical model. The repository maps this model to/from a
``ObjectSnapshot`` using the frozen ``SnapshotMapper`` — no domain logic here.
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

from app.infrastructure.db.types import JSONBType

Base = declarative_base()


class ObjectModel(Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    object_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # JSONB on PostgreSQL; JSON elsewhere.
    metadata_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    audit_json: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
