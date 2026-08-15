"""SQLAlchemy model: ``accreditation_submissions`` (V3 M18, ADR-065).

One row per criterion/indicator submission toward a framework. The lifecycle
is: draft → submitted → approved | rejected, then (when the whole period is
approved) the period is LOCKED — an irreversible attestation. AI may suggest
evidence and draft narratives but NEVER approves evidence or locks a period:
``approved_by`` / ``locked_by`` are human identities, always.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class AccreditationSubmissionModel(TenantStampMixin, Base):
    __tablename__ = "accreditation_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    framework_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    criterion_id: Mapped[str] = mapped_column(String, nullable=False)
    indicator_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    evidence: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    narrative: Mapped[str] = mapped_column(String, nullable=False, default="")
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    period: Mapped[str] = mapped_column(String, nullable=False, default="")
    period_locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
