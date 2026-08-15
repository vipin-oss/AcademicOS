"""V3 M9 security unit tests (ADR-056): deny-by-default, principal, revocation."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.principal import DEFAULT_TENANT, principal_from_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.session_revocation_model import (  # noqa: F401
    SessionRevocationModel,
)
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.permissions.role_based import RoleBasedPermissionEvaluator
from app.infrastructure.persistence.token_revocation_store import (
    SQLTokenRevocationStore,
)


def _p(sub, roles=()) -> dict:
    return {"sub": sub, "roles": list(roles)}


class TestDenyByDefaultObjectAcl:
    def test_missing_acl_fail_open_by_default(self):
        ev = ObjectPermissionEvaluator(deny_by_default=False)
        assert ev.can(principal=_p("u:1"), scope=None, action=PermissionAction.READ)

    def test_missing_acl_denies_when_flag_on(self):
        ev = ObjectPermissionEvaluator(deny_by_default=True)
        assert not ev.can(principal=_p("u:1"), scope=None, action=PermissionAction.READ)

    def test_owner_only_denies_non_owner_when_flag_on(self):
        ev = ObjectPermissionEvaluator(deny_by_default=True)
        scope = '{"owner":"u:bob","readers":[],"writers":[],"managers":[]}'
        assert not ev.can(principal=_p("u:alice"), scope=scope, action=PermissionAction.READ)
        assert ev.can(principal=_p("u:bob"), scope=scope, action=PermissionAction.READ)
        assert ev.can(principal=_p("u:admin", roles=["admin"]), scope=scope, action=PermissionAction.READ)

    def test_explicit_grant_still_allows(self):
        ev = ObjectPermissionEvaluator(deny_by_default=True)
        scope = '{"owner":"u:bob","readers":["u:alice"],"writers":[],"managers":[]}'
        assert ev.can(principal=_p("u:alice"), scope=scope, action=PermissionAction.READ)
        assert not ev.can(principal=_p("u:alice"), scope=scope, action=PermissionAction.WRITE)

    def test_malformed_acl_denies_when_flag_on(self):
        ev = ObjectPermissionEvaluator(deny_by_default=True)
        assert not ev.can(principal=_p("u:1"), scope="{not json", action=PermissionAction.READ)


class TestDenyByDefaultRoleBased:
    def test_roleless_holds_read_write_by_default(self):
        ev = RoleBasedPermissionEvaluator(deny_by_default=False)
        assert ev.can(principal=_p("u:1"), scope=None, action=PermissionAction.READ)
        assert ev.can(principal=_p("u:1"), scope=None, action=PermissionAction.WRITE)

    def test_roleless_denies_when_flag_on(self):
        ev = RoleBasedPermissionEvaluator(deny_by_default=True)
        assert not ev.can(principal=_p("u:1"), scope=None, action=PermissionAction.READ)

    def test_admin_always_allowed(self):
        ev = RoleBasedPermissionEvaluator(deny_by_default=True)
        assert ev.can(principal=_p("u:a", roles=["admin"]), scope=None, action=PermissionAction.MANAGE)


class TestPrincipalContext:
    def test_built_from_live_user(self):
        user = UniversalObject.create(
            ObjectType.USER, "alice", created_by="system", status=ObjectStatus.ACTIVE,
            object_id=ObjectId("obj:user:alice-0001"),
        )
        principal = principal_from_user(user)
        assert principal.sub == "obj:user:alice-0001"
        assert principal.tenant_id == DEFAULT_TENANT
        assert principal.as_dict()["sub"] == "obj:user:alice-0001"


class TestRevocationStore:
    @pytest.fixture()
    def session(self):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        sess = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            yield sess
        finally:
            sess.close()
            engine.dispose()

    def test_add_is_revoked_prune(self, session):
        store = SQLTokenRevocationStore(session)
        store.add("jti-1", "2026-01-01T00:00:00+00:00")
        session.commit()
        assert store.is_revoked("jti-1", now="2025-06-01T00:00:00+00:00") is True
        # past expiry -> not revoked (token already dead by its own exp)
        assert store.is_revoked("jti-1", now="2027-01-01T00:00:00+00:00") is False
        assert store.prune(now="2027-01-01T00:00:00+00:00") == 1
        session.commit()
        assert store.is_revoked("jti-1", now="2025-06-01T00:00:00+00:00") is False

    def test_add_is_idempotent(self, session):
        store = SQLTokenRevocationStore(session)
        store.add("jti-x", "2026-01-01T00:00:00+00:00")
        store.add("jti-x", "2026-01-01T00:00:00+00:00")
        session.commit()
        assert store.is_revoked("jti-x", now="2025-01-01T00:00:00+00:00") is True
