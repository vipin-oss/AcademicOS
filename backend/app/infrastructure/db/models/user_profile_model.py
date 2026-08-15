"""SQLAlchemy model: ``user_profiles`` (V3 M16 wave 1 — user_state).

A typed, indexed projection of the user object's hot operational fields
(username, display name, roles, institution) — the first normalization wave.
Derived data: the USER object (UniversalObject) remains the source of truth;
this table is backfilled idempotently and rebuildable. Reads fall back to the
object store on a miss.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class UserProfileModel(TenantStampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    roles: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    institution: Mapped[str | None] = mapped_column(String, nullable=True)
