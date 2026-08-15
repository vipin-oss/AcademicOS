"""SQLAlchemy model: ``saved_views`` (V3 M13, ADR-060).

A saved ad-hoc query/export definition, stored as JSON. The definition is
compiled to parameterized SQL by :class:`SavedViewCompiler` (never executed
verbatim); the row is owned by its creator (owner_user_id + tenant stamps).
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class SavedViewModel(TenantStampMixin, Base):
    __tablename__ = "saved_views"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
