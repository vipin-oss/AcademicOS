"""SQLAlchemy models: ``organizations`` + ``memberships`` (V3 M15, ADR-062).

An organization is a tenant. ``organizations`` carries the tenant lifecycle
(status, per-tenant storage quota + spend cap); ``memberships`` binds a user to
an organization with a scoped role. The ``tenant_id`` stamp (M3) on every table
is the isolation key: enforcement filters by the principal's tenant.
"""

from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class OrganizationModel(TenantStampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    storage_quota_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spend_cap_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class MembershipModel(TenantStampMixin, Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
