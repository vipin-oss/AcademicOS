"""Unit tests for RoleBasedPermissionEvaluator (Sprint-1 M3 — R4 seam)."""
from __future__ import annotations

import pytest

from app.domain.value_objects.enums import PermissionAction
from app.infrastructure.permissions.role_based import RoleBasedPermissionEvaluator


@pytest.fixture()
def evaluator() -> RoleBasedPermissionEvaluator:
    return RoleBasedPermissionEvaluator()


def test_unauthenticated_principal_has_no_actions(evaluator):
    for action in PermissionAction:
        assert evaluator.can(principal=None, scope=None, action=action) is False


def test_authenticated_without_roles_has_no_actions_by_default(evaluator):
    """2026-09 audit follow-up (P0-2): a roleless authenticated principal
    now holds no actions by default (``security_deny_by_default`` flipped
    on — ADR-056). Only MANAGE-gated admin routes use this evaluator
    today, so ordinary professor routes are unaffected; the legacy
    READ+WRITE default remains available as an explicit opt-out below.
    """
    principal = {"sub": "obj:user:X", "roles": []}
    for action in PermissionAction:
        assert evaluator.can(principal=principal, scope=None, action=action) is False


def test_authenticated_without_roles_has_read_write_when_deny_by_default_disabled():
    legacy = RoleBasedPermissionEvaluator(deny_by_default=False)
    principal = {"sub": "obj:user:X", "roles": []}
    assert legacy.can(principal=principal, scope=None, action=PermissionAction.READ) is True
    assert legacy.can(principal=principal, scope=None, action=PermissionAction.WRITE) is True
    assert legacy.can(principal=principal, scope=None, action=PermissionAction.MANAGE) is False


def test_admin_has_manage_and_everything_below(evaluator):
    principal = {"sub": "obj:user:X", "roles": ["admin"]}
    for action in PermissionAction:
        assert evaluator.can(principal=principal, scope=None, action=action) is True


def test_missing_roles_key_denied_by_default(evaluator):
    principal = {"sub": "obj:user:X"}
    assert evaluator.can(principal=principal, scope=None, action=PermissionAction.READ) is False
    assert evaluator.can(principal=principal, scope=None, action=PermissionAction.MANAGE) is False


def test_missing_roles_key_treated_as_no_roles_when_deny_by_default_disabled():
    legacy = RoleBasedPermissionEvaluator(deny_by_default=False)
    principal = {"sub": "obj:user:X"}
    assert legacy.can(principal=principal, scope=None, action=PermissionAction.READ) is True
    assert legacy.can(principal=principal, scope=None, action=PermissionAction.MANAGE) is False


def test_unknown_role_gets_no_privileges(evaluator):
    # An unknown role must never widen capability.
    principal = {"sub": "obj:user:X", "roles": ["superuser"]}
    assert evaluator.can(principal=principal, scope=None, action=PermissionAction.READ) is False
    assert evaluator.can(principal=principal, scope=None, action=PermissionAction.WRITE) is False
    assert evaluator.can(principal=principal, scope=None, action=PermissionAction.MANAGE) is False
