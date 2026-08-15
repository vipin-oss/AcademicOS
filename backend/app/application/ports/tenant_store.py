"""Application port: tenant (organization) store (V3 M15, ADR-062)."""

from __future__ import annotations

import abc
from dataclasses import dataclass

#: Lifecycle statuses.
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"


@dataclass(frozen=True)
class TenantInfo:
    id: str
    name: str
    status: str
    storage_quota_bytes: int
    spend_cap_usd: float


@dataclass(frozen=True)
class MembershipInfo:
    user_id: str
    role: str


class TenantStore(abc.ABC):
    @abc.abstractmethod
    def create(
        self, *, name: str, storage_quota_bytes: int, spend_cap_usd: float
    ) -> TenantInfo:
        """Create a tenant (idempotent identity minted by the store)."""

    @abc.abstractmethod
    def get(self, organization_id: str) -> TenantInfo | None:
        """Fetch a tenant, or None."""

    @abc.abstractmethod
    def set_status(self, organization_id: str, status: str) -> TenantInfo:
        """Transition a tenant's lifecycle status."""

    @abc.abstractmethod
    def list(self) -> list[TenantInfo]:
        """All tenants, creation order."""

    @abc.abstractmethod
    def add_member(self, *, organization_id: str, user_id: str, role: str) -> None:
        """Bind a user to a tenant with a scoped role."""

    @abc.abstractmethod
    def members(self, organization_id: str) -> list[MembershipInfo]:
        """Members of a tenant."""
