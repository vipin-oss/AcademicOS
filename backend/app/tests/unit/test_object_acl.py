"""Unit tests for the object-level ACL evaluator (Sprint-2 M1)."""
from __future__ import annotations

import json

import pytest

from app.domain.value_objects.enums import PermissionAction
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator


@pytest.fixture()
def evaluator() -> ObjectPermissionEvaluator:
    return ObjectPermissionEvaluator()


def _acl(owner="obj:user:OWNER", readers=None, writers=None, managers=None):
    return json.dumps(
        {
            "owner": owner,
            "readers": readers or [],
            "writers": writers or [],
            "managers": managers or [],
        }
    )


def test_no_acl_denies_by_default(evaluator):
    """2026-09 audit follow-up (P0-2): missing/malformed ACL now denies by
    default (``security_deny_by_default`` flipped on — see ADR-056). This
    replaces the old fail-open assertion; the legacy behaviour is still
    supported and covered below via an explicit opt-out evaluator.
    """
    p = {"sub": "obj:user:ANY", "roles": []}
    for action in PermissionAction:
        assert evaluator.can(principal=p, scope=None, action=action) is False
    # An empty ACL dict also means "no ACL" (status quo).
    assert evaluator.can(principal=p, scope="{}", action=PermissionAction.READ) is False


def test_no_acl_allows_when_deny_by_default_disabled():
    """Legacy fail-open behaviour remains available as an explicit opt-out
    (``deny_by_default=False``), never as the implicit default."""
    legacy = ObjectPermissionEvaluator(deny_by_default=False)
    p = {"sub": "obj:user:ANY", "roles": []}
    for action in PermissionAction:
        assert legacy.can(principal=p, scope=None, action=action) is True
    assert legacy.can(principal=p, scope="{}", action=PermissionAction.READ) is True


def test_owner_only_acl_restricts_to_owner_and_admin_by_default(evaluator):
    """2026-09 audit follow-up (P0-2): an owner-only ACL (no explicit
    readers/writers/managers) now restricts every action — READ, WRITE and
    MANAGE — to the owner or an admin. Previously READ/WRITE stayed open
    to any authenticated user, which is exactly the P0-1 cross-user
    exposure this flag closes off for direct-object-id access.
    """
    owner_only = _acl()  # readers/writers/managers all empty
    any_user = {"sub": "obj:user:ANY", "roles": []}
    assert evaluator.can(principal=any_user, scope=owner_only, action=PermissionAction.READ) is False
    assert evaluator.can(principal=any_user, scope=owner_only, action=PermissionAction.WRITE) is False
    assert evaluator.can(principal=any_user, scope=owner_only, action=PermissionAction.MANAGE) is False
    owner = {"sub": "obj:user:OWNER", "roles": []}
    for action in PermissionAction:
        assert evaluator.can(principal=owner, scope=owner_only, action=action) is True
    admin = {"sub": "obj:user:X", "roles": ["admin"]}
    for action in PermissionAction:
        assert evaluator.can(principal=admin, scope=owner_only, action=action) is True


def test_owner_only_acl_keeps_read_write_open_when_deny_by_default_disabled():
    """Legacy fail-open behaviour remains available as an explicit opt-out:
    READ/WRITE stay open on an owner-only ACL, MANAGE stays ownership-gated
    so the ACL endpoint cannot be used to self-grant."""
    legacy = ObjectPermissionEvaluator(deny_by_default=False)
    owner_only = _acl()
    any_user = {"sub": "obj:user:ANY", "roles": []}
    assert legacy.can(principal=any_user, scope=owner_only, action=PermissionAction.READ) is True
    assert legacy.can(principal=any_user, scope=owner_only, action=PermissionAction.WRITE) is True
    assert legacy.can(principal=any_user, scope=owner_only, action=PermissionAction.MANAGE) is False
    owner = {"sub": "obj:user:OWNER", "roles": []}
    assert legacy.can(principal=owner, scope=owner_only, action=PermissionAction.MANAGE) is True
    admin = {"sub": "obj:user:X", "roles": ["admin"]}
    assert legacy.can(principal=admin, scope=owner_only, action=PermissionAction.MANAGE) is True


def test_unauthenticated_never_allowed(evaluator):
    assert evaluator.can(principal=None, scope=_acl(), action=PermissionAction.READ) is False


def test_owner_has_manage(evaluator):
    p = {"sub": "obj:user:OWNER", "roles": []}
    acl = _acl()
    for action in PermissionAction:
        assert evaluator.can(principal=p, scope=acl, action=action) is True


def test_unknown_user_denied(evaluator):
    p = {"sub": "obj:user:STRANGER", "roles": []}
    acl = _acl(readers=["obj:user:INSIDER"])
    for action in PermissionAction:
        assert evaluator.can(principal=p, scope=acl, action=action) is False


def test_reader_reads_but_does_not_write(evaluator):
    p = {"sub": "obj:user:READER", "roles": []}
    acl = _acl(readers=["obj:user:READER"])
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.READ) is True
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.WRITE) is False
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.MANAGE) is False


def test_writer_writes_but_does_not_manage(evaluator):
    p = {"sub": "obj:user:WRITER", "roles": []}
    acl = _acl(writers=["obj:user:WRITER"])
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.READ) is True
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.WRITE) is True
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.MANAGE) is False


def test_manager_manages(evaluator):
    p = {"sub": "obj:user:MGR", "roles": []}
    acl = _acl(managers=["obj:user:MGR"])
    for action in PermissionAction:
        assert evaluator.can(principal=p, scope=acl, action=action) is True


def test_role_entries_match_by_role(evaluator):
    p = {"sub": "obj:user:X", "roles": ["admin"]}
    acl = _acl(managers=["role:admin"])
    assert evaluator.can(principal=p, scope=acl, action=PermissionAction.MANAGE) is True


def test_malformed_scope_denied_by_default(evaluator):
    """2026-09 audit follow-up (P0-2): a malformed scope is treated the
    same as no ACL — denied by default now, not fail-open."""
    p = {"sub": "obj:user:X", "roles": []}
    assert evaluator.can(principal=p, scope="not-json", action=PermissionAction.READ) is False


def test_malformed_scope_allowed_when_deny_by_default_disabled():
    legacy = ObjectPermissionEvaluator(deny_by_default=False)
    p = {"sub": "obj:user:X", "roles": []}
    assert legacy.can(principal=p, scope="not-json", action=PermissionAction.READ) is True
