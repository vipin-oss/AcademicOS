"""Integration tests for the Auth API (Sprint-1 authentication foundation).

Full HTTP flow against the real app with an in-memory SQLite database:
register -> login -> me -> refresh, plus every failure mode (401/409/422).
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
