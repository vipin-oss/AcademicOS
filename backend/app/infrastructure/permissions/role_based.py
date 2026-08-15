"""Role-based permission evaluator (Sprint-1 M3 — R4 seam implementation).

Maps the SRS §3.2/§3.3 coarse capability classes onto PermissionAction:

- users with the ADMIN role hold MANAGE (and therefore WRITE and READ);
- any authenticated user (no roles assigned) holds READ and WRITE —
  the status-quo behaviour, so nothing regresses;
- unauthenticated principals (principal=None) hold nothing.

The principal dict is built by the auth dependency from the USER object:
    {"sub": "<user id>", "roles": ["admin", ...]}

Policy is data, not code: future roles (auditor = READ-only, etc.) are
one row in the map. Object-level (scoped) ACL is a later milestone (S2)
on the same port.
"""
from __future__ import annotations

from app.application.ports.permission import PermissionEvaluator
from app.domain.value_objects.enums import PermissionAction, UserRole

# Role -> actions. Default (no roles) is READ + WRITE.
_ROLE_ACTIONS: dict[str, set[PermissionAction]] = {
    UserRole.ADMIN.value: {
        PermissionAction.READ,
        PermissionAction.WRITE,
        PermissionAction.MANAGE,
    },
    # V3 M14 (ADR-061): academic roles hold READ + WRITE (never MANAGE — the
    # administrative capability stays admin-only).
    UserRole.PROFESSOR.value: {PermissionAction.READ, PermissionAction.WRITE},
    UserRole.SCHOLAR.value: {PermissionAction.READ, PermissionAction.WRITE},
    UserRole.HOD.value: {PermissionAction.READ, PermissionAction.WRITE},
}
_DEFAULT_ACTIONS: frozenset[PermissionAction] = frozenset(
    {PermissionAction.READ, PermissionAction.WRITE}
)


class RoleBasedPermissionEvaluator(PermissionEvaluator):
    """Decides role-level capability by PermissionAction.

    V3 M9 (ADR-056): ``deny_by_default`` makes a roleless (unassigned)
    principal hold NO actions (fail-closed) instead of the legacy READ+WRITE
    default. Configured postures only move fail-open -> fail-closed.
    """

    def __init__(self, *, deny_by_default: bool | None = None) -> None:
        if deny_by_default is None:
            from app.core.config import settings

            deny_by_default = settings.security_deny_by_default
        self._deny_by_default = deny_by_default

    def can(
        self,
        *,
        principal: dict | None,
        scope: str | None,
        action: PermissionAction,
    ) -> bool:
        del scope  # scoped (object-level) ACL lands in S2; role checks are global
        if principal is None:
            return False
        roles = principal.get("roles") or []
        if not roles:
            if self._deny_by_default:
                return False
            # Authenticated but unassigned: the status-quo capability.
            return action in _DEFAULT_ACTIONS
        allowed: set[PermissionAction] = set()
        for role in roles:
            if role in _ROLE_ACTIONS:
                allowed |= _ROLE_ACTIONS[role]
        return action in allowed
