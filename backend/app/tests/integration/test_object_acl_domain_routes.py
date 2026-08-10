"""Integration tests: object ACL enforcement across domain routes (M26).

Before M26, ``require_object_access`` was applied only to the generic
``/objects`` routes. An ACL set via ``PUT /objects/{id}/acl`` could therefore
be bypassed through every other module route (documents, students, faculty,
research, finance, ...) because those routers enforced authentication only.

These tests pin the router-level enforcement (``require_object_acl``):

- a user explicitly denied by an object's ACL gets 403 on module detail
  routes, document download, object update and object delete;
- the owner keeps access;
- unauthenticated requests still get 401;
- the pre-ACL status quo (no ACL metadata) stays open to any authenticated
  user.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.main import app

API = "/api/v1"

# One generic object id is enough: the ACL dependency runs BEFORE the handler,
# so a denied user must receive 403 regardless of the module's type checks.
MODULE_DETAIL_GETS = [
    "/api/v1/objects/{oid}",
    "/api/v1/documents/{oid}",
    "/api/v1/documents/{oid}/download",
    "/api/v1/students/{oid}",
    "/api/v1/faculty/{oid}",
    "/api/v1/publications/{oid}",
    "/api/v1/research/projects/{oid}",
    "/api/v1/research/grants/{oid}",
    "/api/v1/finance/proposals/{oid}",
    "/api/v1/committees/{oid}",
    "/api/v1/events/{oid}",
    "/api/v1/teaching/classes/{oid}",
    "/api/v1/productivity/tasks/{oid}",
    "/api/v1/intake/sessions/{oid}",
    "/api/v1/assistant/conversations/{oid}",
]


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override():
        yield session

    current = {}

    def _fake_user():
        user = current.get("user")
        if user is None:
            from app.core.exceptions import UnauthorizedError

            raise UnauthorizedError("Missing bearer token")
        return user

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_current_user] = _fake_user

    user_a = UniversalObject.create(
        object_type=ObjectType.USER,
        title="user.a",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:acl-a-0001"),
    )
    user_b = UniversalObject.create(
        object_type=ObjectType.USER,
        title="user.b",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:acl-b-0002"),
    )

    def set_user(user):
        current["user"] = user

    with TestClient(app) as client:
        yield _Harness(
            client=client,
            session=session,
            user_a=user_a,
            user_b=user_b,
            set_user=set_user,
        )

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


class _Harness:
    def __init__(self, *, client, session, user_a, user_b, set_user):
        self.client = client
        self.session = session
        self.user_a = user_a
        self.user_b = user_b
        self.set_user = set_user

    def create_owned_object(self, title="Private record") -> str:
        """Create an object as user A and lock its ACL to user A only."""
        self.set_user(self.user_a)
        resp = self.client.post(
            f"{API}/objects",
            json={
                "object_type": "document",
                "title": title,
                "created_by": str(self.user_a.id),
                "status": "active",
            },
        )
        assert resp.status_code == 201, resp.text
        oid = resp.json()["id"]
        acl = self.client.put(
            f"{API}/objects/{oid}/acl",
            json={
                "readers": [str(self.user_a.id)],
                "writers": [str(self.user_a.id)],
                "managers": [str(self.user_a.id)],
            },
        )
        assert acl.status_code == 200, acl.text
        return oid


@pytest.mark.parametrize("path", MODULE_DETAIL_GETS)
def test_denied_user_gets_403_on_module_detail_routes(harness, path):
    oid = harness.create_owned_object()
    harness.set_user(harness.user_b)
    resp = harness.client.get(path.format(oid=oid))
    assert resp.status_code == 403, f"{path} -> {resp.status_code} {resp.text[:120]}"


def test_denied_user_gets_403_on_object_update_and_delete(harness):
    oid = harness.create_owned_object()
    harness.set_user(harness.user_b)
    update = harness.client.put(
        f"{API}/objects/{oid}", json={"updated_by": "user.b", "status": "archived"}
    )
    assert update.status_code == 403, update.text
    delete = harness.client.delete(f"{API}/objects/{oid}")
    assert delete.status_code == 403, delete.text


def test_denied_user_cannot_rewrite_the_acl(harness):
    oid = harness.create_owned_object()
    harness.set_user(harness.user_b)
    resp = harness.client.put(
        f"{API}/objects/{oid}/acl",
        json={"readers": [str(harness.user_b.id)]},
    )
    assert resp.status_code == 403, resp.text


def test_owner_keeps_access_after_restricting_acl(harness):
    oid = harness.create_owned_object()
    harness.set_user(harness.user_a)
    resp = harness.client.get(f"{API}/objects/{oid}")
    assert resp.status_code == 200, resp.text
    acl = harness.client.get(f"{API}/objects/{oid}/acl")
    assert acl.status_code == 200, acl.text
    assert acl.json()["owner"] == str(harness.user_a.id)


def test_unauthenticated_request_still_gets_401(harness):
    oid = harness.create_owned_object()
    harness.set_user(None)
    resp = harness.client.get(f"{API}/objects/{oid}")
    assert resp.status_code == 401, resp.text


def test_no_acl_metadata_preserves_open_status_quo(harness):
    """Without ACL metadata any authenticated user can read — pre-M26 behavior."""
    harness.set_user(harness.user_a)
    resp = harness.client.post(
        f"{API}/objects",
        json={
            "object_type": "course",
            "title": "Open course",
            "created_by": str(harness.user_a.id),
            "status": "active",
        },
    )
    assert resp.status_code == 201, resp.text
    oid = resp.json()["id"]
    harness.set_user(harness.user_b)
    got = harness.client.get(f"{API}/objects/{oid}")
    assert got.status_code == 200, got.text
