"""Server-side principal context (V3 M9, ADR-056).

``PrincipalContext`` is the single, server-built shape for an authenticated
caller's security identity. It is constructed ONLY server-side from the live
USER object (roles and tenant are read from authoritative state, never from
client-supplied claims), so a client can never forge a role or a tenant.

It carries ``tenant_id`` so that M9 tenant enforcement (and M15 multi-tenancy)
can filter queries *before* aggregation — the QueryScope discipline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.use_cases.auth.helpers import get_roles
from app.domain.entities.object import UniversalObject

#: The single-tenant present's tenant id (the M3 stamp default).
DEFAULT_TENANT = "default"


@dataclass(frozen=True)
class PrincipalContext:
    """A server-built security identity (sub + roles + tenant)."""

    sub: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    tenant_id: str = DEFAULT_TENANT

    def as_dict(self) -> dict:
        """The ``{"sub", "roles"}`` shape the R4 evaluator port consumes."""
        return {"sub": self.sub, "roles": list(self.roles)}


def principal_from_user(user: UniversalObject, *, tenant_id: str | None = None) -> PrincipalContext:
    """Build a PrincipalContext from the authenticated USER object.

    Roles come from the live object (never a token claim); tenant defaults to
    the single-tenant present unless the caller supplies one.
    """
    return PrincipalContext(
        sub=str(user.id),
        roles=tuple(get_roles(user)),
        tenant_id=tenant_id or DEFAULT_TENANT,
    )


__all__ = ["DEFAULT_TENANT", "PrincipalContext", "principal_from_user"]
