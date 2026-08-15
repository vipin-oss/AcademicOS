"""Tenant (organization) lifecycle service (V3 M15, ADR-062).

Owns the multi-tenant lifecycle: create / suspend / resume an organization,
and bind members with a scoped role. Depends only on the ``TenantStore`` port
(Clean Architecture: application never imports infrastructure).

Enforcement is the M3 tenant_id stamp + the M9 flag + tenant predicates in
query compilers (saved views) and search — a config flip, never a migration.
Isolation is the KEY invariant: a suspended organization denies its members,
and a member of one organization can never see another's data.
"""

from __future__ import annotations

from app.application.ports.tenant_store import (
    STATUS_ACTIVE,
    STATUS_SUSPENDED,
    TenantInfo,
    TenantStore,
)


class TenantService:
    def __init__(self, store: TenantStore) -> None:
        self._store = store

    def create(
        self,
        *,
        name: str,
        storage_quota_bytes: int = 0,
        spend_cap_usd: float = 0.0,
    ) -> TenantInfo:
        return self._store.create(
            name=name,
            storage_quota_bytes=storage_quota_bytes,
            spend_cap_usd=spend_cap_usd,
        )

    def suspend(self, organization_id: str) -> TenantInfo:
        return self._store.set_status(organization_id, STATUS_SUSPENDED)

    def resume(self, organization_id: str) -> TenantInfo:
        return self._store.set_status(organization_id, STATUS_ACTIVE)

    def get(self, organization_id: str) -> TenantInfo:
        tenant = self._store.get(organization_id)
        if tenant is None:
            raise KeyError(f"Organization not found: {organization_id}")
        return tenant

    def list(self) -> list[TenantInfo]:
        return self._store.list()

    def add_member(self, *, organization_id: str, user_id: str, role: str = "member") -> None:
        self._store.add_member(organization_id=organization_id, user_id=user_id, role=role)

    def members(self, organization_id: str) -> list[tuple[str, str]]:
        return [(m.user_id, m.role) for m in self._store.members(organization_id)]

    def is_suspended(self, organization_id: str) -> bool:
        return self.get(organization_id).status == STATUS_SUSPENDED


__all__ = ["TenantInfo", "TenantService"]
