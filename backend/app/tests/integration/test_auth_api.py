"""Integration tests for the Auth API (Sprint-1 authentication foundation).

Full HTTP flow against the real app with an in-memory SQLite database:
register -> login -> me -> refresh, plus every failure mode (401/409/422).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.main import app

API = "/api/v1/auth"


@pytest.fixture()
def client():
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

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _register(client, username="dr.ananya", password="correct-horse-battery"):
    return client.post(
        f"{API}/register",
        json={"username": username, "password": password},
    )


def _login(client, username="dr.ananya", password="correct-horse-battery"):
    return client.post(f"{API}/login", json={"username": username, "password": password})


def test_full_auth_flow(client):
    # register -> 201 user
    reg = _register(client)
    assert reg.status_code == 201
    body = reg.json()
    assert body["username"] == "dr.ananya"
    assert body["id"].startswith("obj:user:")

    # duplicate register -> 409
    assert _register(client).status_code == 409

    # login -> tokens
    login = _login(client)
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    # me with the access token -> 200
    me = client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "dr.ananya"

    # refresh -> fresh pair; the new access token works
    refreshed = client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    me2 = client.get(f"{API}/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me2.status_code == 200


def test_login_failures(client):
    _register(client)
    # wrong password -> 401
    assert _login(client, password="wrong-password").status_code == 401
    # unknown user -> 401 (same code, no enumeration)
    assert _login(client, username="ghost").status_code == 401
    # validation -> 422
    assert _login(client, password="").status_code == 422


def test_me_requires_valid_access_token(client):
    _register(client)
    login = _login(client).json()

    # no token
    assert client.get(f"{API}/me").status_code == 401
    # garbage token
    assert (
        client.get(f"{API}/me", headers={"Authorization": "Bearer garbage"}).status_code
        == 401
    )
    # a refresh token must not satisfy a protected endpoint
    assert (
        client.get(
            f"{API}/me", headers={"Authorization": f"Bearer {login['refresh_token']}"}
        ).status_code
        == 401
    )


def test_refresh_failures(client):
    _register(client)
    login = _login(client).json()

    # an access token is not a refresh token
    assert (
        client.post(f"{API}/refresh", json={"refresh_token": login["access_token"]}).status_code
        == 401
    )
    # garbage
    assert client.post(f"{API}/refresh", json={"refresh_token": "garbage"}).status_code == 401
    # empty
    assert client.post(f"{API}/refresh", json={"refresh_token": "  "}).status_code == 422


def test_register_validation(client):
    assert _register(client, username="   ", password="correct-horse-battery").status_code == 422
    assert _register(client, username="dr.ananya", password="short").status_code == 422


# ------------------------------------------------------- adversarial regressions
# Findings from the independent security audit (Sprint-1):


def test_password_hash_never_exposed_via_generic_objects_api(client):
    """A registered user's credential must not leak through the generic
    object endpoints — not even to an authenticated caller (the projection
    excludes L1_SYSTEM metadata)."""
    reg = _register(client, username="hash.victim", password="super-secret-pw")
    uid = reg.json()["id"]
    access = _login(client, username="hash.victim", password="super-secret-pw").json()[
        "access_token"
    ]
    auth_headers = {"Authorization": f"Bearer {access}"}

    detail = client.get(f"/api/v1/objects/{uid}", headers=auth_headers)
    assert detail.status_code == 200
    assert "auth.password_hash" not in detail.json().get("metadata", {})

    listing = client.get("/api/v1/objects?object_type=user", headers=auth_headers)
    assert listing.status_code == 200
    for item in listing.json().get("items", []):
        assert "auth.password_hash" not in item.get("metadata", {})

    # Unauthenticated callers are rejected outright now that the objects
    # API requires a valid access token.
    assert client.get(f"/api/v1/objects/{uid}").status_code == 401


def test_token_without_sub_claim_is_401_not_500(client):
    """A token signed without a subject is malformed input — 401, never 500."""
    import datetime

    import jwt as pyjwt

    from app.core.config import settings

    no_sub = pyjwt.encode(
        {
            "type": "access",
            "iat": datetime.datetime.now(datetime.UTC),
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = client.get(f"{API}/me", headers={"Authorization": f"Bearer {no_sub}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"

    no_sub_refresh = pyjwt.encode(
        {
            "type": "refresh",
            "iat": datetime.datetime.now(datetime.UTC),
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = client.post(f"{API}/refresh", json={"refresh_token": no_sub_refresh})
    assert resp.status_code == 401


def test_expired_token_is_401(client):
    """An expired access token is rejected as 401."""
    import datetime

    import jwt as pyjwt

    from app.core.config import settings

    expired = pyjwt.encode(
        {
            "sub": "obj:user:DEADBEEF",
            "type": "access",
            "iat": datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2),
            "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = client.get(f"{API}/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_authenticated_identity_propagates_to_object_ownership(client):
    """Sprint-1 M2 — the authenticated user is the execution context: an
    object created through the API records the user's id in its audit
    trail, regardless of any client-supplied identity field."""
    reg = _register(client, username="owner.user", password="owner-pass-123")
    uid = reg.json()["id"]
    access = _login(client, username="owner.user", password="owner-pass-123").json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {access}"}

    # Client sends a spoofed identity; the authenticated principal must win.
    created = client.post(
        "/api/v1/objects",
        headers=headers,
        json={
            "object_type": "course",
            "title": "Ownership Course",
            "created_by": "spoofed:identity",
            "status": "draft",
        },
    )
    assert created.status_code == 201
    oid = created.json()["id"]

    detail = client.get(f"/api/v1/objects/{oid}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    # The audit trail records the authenticated user, not the spoof.
    assert body["created_by"] == uid
    assert body["id"].startswith("obj:course:")


def test_authenticated_identity_propagates_to_updates(client):
    reg = _register(client, username="updater.user", password="updater-pass-123")
    uid = reg.json()["id"]
    access = _login(client, username="updater.user", password="updater-pass-123").json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {access}"}

    created = client.post(
        "/api/v1/objects",
        headers=headers,
        json={"object_type": "course", "title": "Upd Course", "created_by": "x", "status": "draft"},
    ).json()
    updated = client.put(
        f"/api/v1/objects/{created['id']}",
        headers=headers,
        json={"updated_by": "spoofed:updater", "status": "active"},
    )
    assert updated.status_code == 200
    assert updated.json()["created_by"] == uid


# ------------------------------------------------- Sprint-1 M3 — RBAC


def _promote(client, username):
    """Give a user the admin role through the domain (test setup, not a
    bypass: enforcement still runs through require_permission)."""
    from app.application.use_cases.auth.helpers import find_user, set_roles
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    session = next(app.dependency_overrides[get_db]())
    repo = SQLAlchemyObjectRepository(session)
    user = find_user(repo, username)
    set_roles(user, ["admin"])
    repo.save(user)


def _register_and_login(client, username, password):
    client.post(f"{API}/register", json={"username": username, "password": password})
    return client.post(f"{API}/login", json={"username": username, "password": password}).json()[
        "access_token"
    ]


def test_role_assignment_requires_admin(client):
    """Non-admin users get 403 on user management; admins succeed."""
    admin_token = _register_and_login(client, "rbac.admin", "rbac-admin-pass")
    _promote(client, "rbac.admin")
    user_token = _register_and_login(client, "rbac.user", "rbac-user-pass-1")
    target = client.get(f"{API}/me", headers={"Authorization": f"Bearer {user_token}"}).json()

    # Non-admin: 403 on both list and assign.
    assert (
        client.get(f"{API}/users", headers={"Authorization": f"Bearer {user_token}"}).status_code
        == 403
    )
    assert (
        client.put(
            f"{API}/users/{target['id']}/roles",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"roles": ["admin"]},
        ).status_code
        == 403
    )

    # Admin: list shows both users; assignment works.
    listing = client.get(f"{API}/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert listing.status_code == 200
    assert {u["username"] for u in listing.json()} == {"rbac.admin", "rbac.user"}

    assigned = client.put(
        f"{API}/users/{target['id']}/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"roles": ["admin"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["roles"] == ["admin"]

    # The promoted user can now manage too.
    assert (
        client.get(f"{API}/users", headers={"Authorization": f"Bearer {user_token}"}).status_code
        == 200
    )


def test_unauthenticated_user_management_is_401(client):
    assert client.get(f"{API}/users").status_code == 401
    assert (
        client.put(f"{API}/users/obj:user:X/roles", json={"roles": ["admin"]}).status_code
        == 401
    )


def test_unknown_role_assignment_is_422(client):
    admin_token = _register_and_login(client, "rbac.admin2", "rbac-admin-pass")
    _promote(client, "rbac.admin2")
    target = _register_and_login(client, "rbac.user2", "rbac-user-pass-1")
    target_id = client.get(f"{API}/me", headers={"Authorization": f"Bearer {target}"}).json()["id"]
    resp = client.put(
        f"{API}/users/{target_id}/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"roles": ["superuser"]},
    )
    assert resp.status_code == 422


def test_me_reports_roles(client):
    token = _register_and_login(client, "rbac.me", "rbac-me-pass-1")
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["roles"] == []


def test_generic_object_api_cannot_grant_roles(client):
    """Security regression (Sprint-1 M3): the generic objects API must not
    write auth.* metadata or create USER objects — privilege escalation
    via auth.roles would otherwise be trivial."""
    token = _register_and_login(client, "escalation.user", "escalation-pass-1")
    H = {"Authorization": f"Bearer {token}"}
    uid = client.get(f"{API}/me", headers=H).json()["id"]

    # 1. Self-assign admin via the generic update endpoint -> 422.
    resp = client.put(
        f"/api/v1/objects/{uid}",
        headers=H,
        json={"updated_by": "x", "metadata": [{"key": "auth.roles", "value": '["admin"]'}]},
    )
    assert resp.status_code == 422
    me = client.get(f"{API}/me", headers=H)
    assert me.json()["roles"] == []

    # 2. Mint a USER object via the generic create endpoint -> 422.
    resp = client.post(
        "/api/v1/objects",
        headers=H,
        json={
            "object_type": "user",
            "title": "fake.admin",
            "created_by": "x",
            "metadata": [{"key": "auth.roles", "value": '["admin"]'}],
        },
    )
    assert resp.status_code == 422
    listing = client.get("/api/v1/objects?object_type=user", headers=H)
    assert all(u["title"] != "fake.admin" for u in listing.json().get("items", []))
