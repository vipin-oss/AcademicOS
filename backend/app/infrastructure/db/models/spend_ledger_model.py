"""SQLAlchemy model: ``spend_ledger`` (V3 M12, ADR-059).

Append-only spend audit for AI calls: one row per provider generation, keyed
by ``id``, carrying the tenant/user, the provider/model, token counts, and the
estimated cost. The budget policy reads the aggregate; the ledger is the
immutable evidence (never updated, never deleted).
"""

from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class SpendLedgerModel(TenantStampMixin, Base):
    __tablename__ = "spend_ledger"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
