"""SQLAlchemy model for the single ``objects`` table.

One table, one row per Universal Object. Structured columns (id, type, title,
status, version) are scalar; the rich, schema-less parts (metadata, audit) are
stored as JSONB on PostgreSQL (and as JSON on other engines via ``JSONBType``).
Graph edges live in ``object_relationships`` (see ``object_relationship_model``)
— R1 Object Graph physical model. The repository maps this model to/from a
``ObjectSnapshot`` using the frozen ``SnapshotMapper`` — no domain logic here.
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

from app.infrastructure.db.types import JSONBType

Base = declarative_base()


class TenantStampMixin:
    """V3 M3 — tenancy stamping columns (columns only, no enforcement).

    Every table carries ``tenant_id`` + ``owner_user_id`` so the retrofit
    (blueprint V3 §M3, correcting audit A7) never has to rewrite the schema
    later. In the single-tenant present both default to ``'default'``.
    Enforcement — reads filtered by tenant, ownership checks — is M9; here the
    columns simply exist, are backfilled, and are indexed. Because both columns
    are ``nullable=False`` with a server default, no write path can forget to
    stamp them (ORM inserts include the Python default; raw SQL inserts get the
    server default), and post-backfill ``tenant_id`` is NULL-free by
    construction.
    """

    tenant_id: Mapped[str] = mapped_column(
        String, nullable=False, default="default", server_default="default", index=True
    )
    owner_user_id: Mapped[str] = mapped_column(
        String, nullable=False, default="default", server_default="default", index=True
    )


class SearchYearMixin:
    """2026-09 audit follow-up (P1): a materialized, indexed year column so
    year-filtered listings can run as a real SQL predicate instead of
    loading every row of a type and filtering in Python (measured 46x
    slower at just 6,000 rows — see docs/architecture/adr/ for the
    benchmark). Nullable: only object types that populate it (events, to
    start) get the fast path; others keep the existing behaviour until
    extended the same way. Populated by the repository's ``save()`` from a
    per-object-type date/year metadata key — see
    ``_extract_search_year`` in ``sqlalchemy_object_repository.py``.
    """

    search_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class ObjectModel(TenantStampMixin, SearchYearMixin, Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    object_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # JSONB on PostgreSQL; JSON elsewhere.
    metadata_json: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    audit_json: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
