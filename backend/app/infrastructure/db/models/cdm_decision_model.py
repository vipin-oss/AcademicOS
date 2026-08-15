"""SQLAlchemy model: ``cdm_decisions`` — L3 CDM-block confirmation audit.

Append-only, idempotent-by-``decision_id`` audit of human decisions on a CDM
block (approve/reject). ``subject_id`` = the CDM block_id. Mirrors
``claim_decisions`` but for the structured-document block plane.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class CdmDecisionModel(TenantStampMixin, Base):
    __tablename__ = "cdm_decisions"
    __table_args__ = (
        Index("ix_cdm_decisions_block_id", "subject_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)  # block_id
    decision: Mapped[str] = mapped_column(String, nullable=False)  # approve/reject
    reviewer: Mapped[str] = mapped_column(String, nullable=False)
    previous_status: Mapped[str] = mapped_column(String, nullable=False)
    resulting_status: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
