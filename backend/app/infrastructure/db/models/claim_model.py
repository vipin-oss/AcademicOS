"""SQLAlchemy model: ``claims`` — the L1 claim store (ADR-002 + ADR-019).

The single AI-visible fact source. Each row is one proposed/confirmed/rejected/
superseded fact bound to a predicate (``predicate_id`` + version) from the
registry-driven catalogue. Values that fail validation are stored as ``raw``
plus the source text — never dropped. ``claim_id`` is the idempotency key.
``acl_scope`` carries the source ACL scope (ADR-009).
"""

from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class ClaimModel(TenantStampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        Index("ix_claims_source_document", "source_document_id"),
        Index("ix_claims_predicate", "predicate_id", "status"),
        # V3 M5 (audit A1): typed, indexed columns so rung-0 fact lookups are a
        # single indexed scan, not a JSONB scan (ORDER BY / BETWEEN / SUM over
        # `value` cannot use an index). Writer-populated (not GENERATED): the
        # JSON extraction expression is dialect-specific (Postgres JSONB vs
        # SQLite json_extract) and not IMMUTABLE-portable, so the claim writer
        # populates them — same result, one extra write path (blueprint A1).
        Index("ix_claims_predicate_number", "predicate_id", "value_number"),
        Index("ix_claims_predicate_date", "predicate_id", "value_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    predicate_id: Mapped[str] = mapped_column(String, nullable=False)
    predicate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    value_schema: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provenance: Mapped[str] = mapped_column(String, nullable=False)
    fact_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    supersedes_claim_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # V3 M5 — typed projections of ``value`` (writer-populated; see index note).
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    value_date: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Claim {self.claim_id} {self.predicate_id} {self.status}>"
