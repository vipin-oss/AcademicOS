"""Contract tests for the R4 permission planning seam.

The seam is interfaces + contracts only (no enforcement — that lands in S2
edge ACL and S5 search pre-filtering). These tests pin:
  - the action vocabulary (SRS §3.3 capability-matrix classes),
  - the port's abstractness (a real evaluator must implement ``can``),
  - the backward-compatible default (allow-all) across every input class.
"""
from __future__ import annotations

import pytest

from app.application.ports.permission import PermissionEvaluator
from app.domain.value_objects.enums import PermissionAction
from app.infrastructure.permissions.allow_all import AllowAllPermissionEvaluator


def test_permission_action_vocabulary():
    assert [a.value for a in PermissionAction] == ["read", "write", "manage"]
    # The capability-matrix classes map 1:1 onto the vocabulary.
    assert PermissionAction.READ.value == "read"
    assert PermissionAction.WRITE.value == "write"
    assert PermissionAction.MANAGE.value == "manage"


def test_port_is_abstract():
    with pytest.raises(TypeError):
        PermissionEvaluator()  # type: ignore[abstract]


def test_allow_all_permits_everything():
    evaluator = AllowAllPermissionEvaluator()
    for action in PermissionAction:
        # unauthenticated / unscoped
        assert evaluator.can(principal=None, scope=None, action=action) is True
        # authenticated, scoped
        assert evaluator.can(
            principal={"sub": "faculty:1"}, scope="dept:cs", action=action
        ) is True
        # authenticated, unscoped
        assert evaluator.can(principal={"sub": "faculty:1"}, scope=None, action=action) is True


def test_allow_all_accepts_keyword_contract_only():
    """The port signature is keyword-only — positionals must not silently pass."""
    evaluator = AllowAllPermissionEvaluator()
    with pytest.raises(TypeError):
        evaluator.can(None, None, PermissionAction.READ)  # type: ignore[misc]
