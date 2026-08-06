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
}
_DEFAULT_ACTIONS: frozenset[PermissionAction] = frozenset(
    {PermissionAction.READ, PermissionAction.WRITE}
)


class RoleBasedPermissionEvaluator(PermissionEvaluator):
    """Decides role-level capability by PermissionAction."""

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
            # Authenticated but unassigned: the status-quo capability.
            return action in _DEFAULT_ACTIONS
        allowed: set[PermissionAction] = set()
        for role in roles:
            if role in _ROLE_ACTIONS:
                allowed |= _ROLE_ACTIONS[role]
        return action in allowed
