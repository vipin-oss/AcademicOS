"""SQL implementation of the tenant store (V3 M15, ADR-062)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.tenant_store import (
    MembershipInfo,
    TenantInfo,
    TenantStore,
)
from app.infrastructure.db.models.organization_model import (
    MembershipModel,
    OrganizationModel,
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class SQLTenantStore(TenantStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, *, name: str, storage_quota_bytes: int, spend_cap_usd: float
    ) -> TenantInfo:
        tenant = OrganizationModel(
            id=uuid.uuid4().hex,
            name=name,
            status="active",
            storage_quota_bytes=storage_quota_bytes,
            spend_cap_usd=spend_cap_usd,
            created_at=_utcnow(),
        )
        self._session.add(tenant)
        self._session.commit()
        return _to_info(tenant)

    def get(self, organization_id: str) -> TenantInfo | None:
        row = self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == organization_id)
        ).scalars().first()
        return _to_info(row) if row else None

    def set_status(self, organization_id: str, status: str) -> TenantInfo:
        row = self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == organization_id)
        ).scalars().first()
        if row is None:
            raise KeyError(f"Organization not found: {organization_id}")
        row.status = status
        self._session.commit()
        return _to_info(row)

    def list(self) -> list[TenantInfo]:
        rows = self._session.execute(
            select(OrganizationModel).order_by(OrganizationModel.created_at)
        ).scalars().all()
        return [_to_info(r) for r in rows]

    def add_member(self, *, organization_id: str, user_id: str, role: str) -> None:
        if self.get(organization_id) is None:
            raise KeyError(f"Organization not found: {organization_id}")
        self._session.add(
            MembershipModel(
                id=uuid.uuid4().hex,
                organization_id=organization_id,
                user_id=user_id,
                role=role,
                created_at=_utcnow(),
            )
        )
        self._session.commit()

    def members(self, organization_id: str) -> list[MembershipInfo]:
        rows = self._session.execute(
            select(MembershipModel).where(MembershipModel.organization_id == organization_id)
        ).scalars().all()
        return [MembershipInfo(user_id=r.user_id, role=r.role) for r in rows]


def _to_info(row: OrganizationModel) -> TenantInfo:
    return TenantInfo(
        id=row.id,
        name=row.name,
        status=row.status,
        storage_quota_bytes=row.storage_quota_bytes,
        spend_cap_usd=row.spend_cap_usd,
    )
