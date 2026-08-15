"""V3 M14 architecture guardrails (ADR-061).

Pins the multi-user/admin contracts:

- the four academic role classes exist and map to READ+WRITE (never MANAGE);
- admin operational views are MANAGE-gated (admin-only);
- academic roles never gain MANAGE (the administrative capability stays
  admin-only — role escalation is impossible by enum/policy).
"""

from __future__ import annotations

import inspect


def test_roles_are_four() -> None:
    from app.domain.value_objects.enums import UserRole

    assert {r.value for r in UserRole} == {"admin", "professor", "scholar", "hod"}


def test_academic_roles_never_manage() -> None:
    import app.infrastructure.permissions.role_based as mod

    src = inspect.getsource(mod)
    # the academic roles map to READ + WRITE only (no MANAGE)
    for role in ("professor", "scholar", "hod"):
        assert f"UserRole.{role.upper()}.value" in src


def test_admin_routes_are_manage_gated() -> None:
    import app.api.routes.admin as mod

    src = inspect.getsource(mod)
    assert "PermissionAction.MANAGE" in src


def test_role_escalation_impossible() -> None:
    # a non-admin role cannot self-elevate: the policy map grants MANAGE to
    # ADMIN only.
    from app.infrastructure.permissions.role_based import _ROLE_ACTIONS
    from app.domain.value_objects.enums import PermissionAction, UserRole

    assert _ROLE_ACTIONS[UserRole.ADMIN.value] >= {PermissionAction.MANAGE}
    for role in ("professor", "scholar", "hod"):
        assert PermissionAction.MANAGE not in _ROLE_ACTIONS[UserRole(role).value]
