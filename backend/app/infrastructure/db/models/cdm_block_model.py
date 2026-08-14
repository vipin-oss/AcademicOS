"""SQLAlchemy model: ``cdm_blocks`` — structured-document block store (L1, §11).

Format-agnostic block representation. One row per block of the structured
document model (heading/section/table/figure/caption/footnote/header/footer/
equation/image_region/diagram/slide/list/...). Reading order is carried as
data (``order`` + ``parent_block_id``). ``payload`` is the block content and
may reference spans; ``acl_scope`` carries the source ACL scope (ADR-009);
``extraction_confidence`` is the ADR-004 extraction-level confidence (distinct
from any fact confidence on claims derived from the block).
"""

from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class CdmBlockModel(TenantStampMixin, Base):
    __tablename__ = "cdm_blocks"
    __table_args__ = (
        Index("ix_cdm_blocks_document", "document_id", "version"),
        Index("ix_cdm_blocks_parent", "parent_block_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    block_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    parent_block_id: Mapped[str | None] = mapped_column(String, nullable=True)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
