"""SQLAlchemy model: ``session_revocations`` — revoked token ids (V3 M9).

A durable denylist of revoked token ``jti``s (ADR-056 "revocation"). A token is
revoked on logout (and on rotation, later); rows are pruned once their
``expires_at`` is past the token's own absolute expiry, so the table stays
bounded. ``jti`` is the idempotency key.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class SessionRevocationModel(TenantStampMixin, Base):
    __tablename__ = "session_revocations"

    jti: Mapped[str] = mapped_column(String, primary_key=True)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)
