"""SQLAlchemy model: ``claim_decisions`` — L3 confirmation/correction audit.

Append-only, idempotent-by-``decision_id`` audit of every human decision on a
claim (approve/reject/correct). Rows are never updated — the full history is
preserved by construction. This is claim-scoped (NOT conversation-scoped like
``review_decisions``), so document decisions never couple to assistant reviews.

``subject_id`` = the claim_id. ``previous_status`` and ``resulting_status``
reconstruct the lifecycle from the log alone. ``acl_scope`` records the scope
at decision time. ``eval_run_id`` is a soft reference (rejections can feed
evaluation, ADR-032).
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class ClaimDecisionModel(TenantStampMixin, Base):
    __tablename__ = "claim_decisions"
    __table_args__ = (
        Index("ix_claim_decisions_claim_id", "subject_id"),
        Index("ix_claim_decisions_reviewer", "reviewer", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)  # claim_id
    decision: Mapped[str] = mapped_column(String, nullable=False)  # approve/reject/correct
    reviewer: Mapped[str] = mapped_column(String, nullable=False)
    previous_status: Mapped[str] = mapped_column(String, nullable=False)
    resulting_status: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    eval_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
