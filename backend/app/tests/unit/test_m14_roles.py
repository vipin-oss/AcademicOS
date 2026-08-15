"""V3 M14 role tests (ADR-061): the four academic role classes."""

from __future__ import annotations

from app.domain.value_objects.enums import PermissionAction, UserRole
from app.infrastructure.permissions.role_based import RoleBasedPermissionEvaluator


def test_four_role_classes_exist():
    assert {r.value for r in UserRole} == {"admin", "professor", "scholar", "hod"}


def test_admin_holds_manage():
    ev = RoleBasedPermissionEvaluator(deny_by_default=False)
    assert ev.can(principal={"sub": "u", "roles": ["admin"]}, scope=None, action=PermissionAction.MANAGE)


def test_academic_roles_hold_read_write_not_manage():
    ev = RoleBasedPermissionEvaluator(deny_by_default=False)
    for role in ("professor", "scholar", "hod"):
        assert ev.can(principal={"sub": "u", "roles": [role]}, scope=None, action=PermissionAction.READ)
        assert ev.can(principal={"sub": "u", "roles": [role]}, scope=None, action=PermissionAction.WRITE)
        assert not ev.can(principal={"sub": "u", "roles": [role]}, scope=None, action=PermissionAction.MANAGE)


def test_roleless_unchanged():
    ev = RoleBasedPermissionEvaluator(deny_by_default=False)
    assert ev.can(principal={"sub": "u", "roles": []}, scope=None, action=PermissionAction.READ)
    assert not ev.can(principal={"sub": "u", "roles": []}, scope=None, action=PermissionAction.MANAGE)
