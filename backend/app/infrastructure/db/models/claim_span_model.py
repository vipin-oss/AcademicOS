"""SQLAlchemy model: ``claim_spans`` — polymorphic span provenance (ADR-003).

One row per (claim, span): a claim binds >= 1 source-local region. The span is
stored polymorphically — ``span_kind`` discriminator + scalar anchors + a
``region`` JSON payload (bbox / cell ref / opaque engine region). Page/block/
char are among the supported kinds, never the universal model.
"""

from __future__ import annotations

from sqlalchemy import Column, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class ClaimSpanModel(TenantStampMixin, Base):
    __tablename__ = "claim_spans"
    __table_args__ = (
        Index("ix_claim_spans_claim_id", "claim_id"),
        Index("ix_claim_spans_source", "source_id", "span_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    span_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    claim_id: Mapped[str] = mapped_column(String, nullable=False)
    span_kind: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_id: Mapped[str | None] = mapped_column(String, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_id: Mapped[str | None] = mapped_column(String, nullable=True)
    slide: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSONBType, nullable=True)
    region: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
