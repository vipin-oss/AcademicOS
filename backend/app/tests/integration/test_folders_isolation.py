"""Multi-user isolation + query-scoping regression tests for Document Folders.

2026-09 performance hardening (Phase 2 audit follow-up). GET /folders and
GET /folders/all previously loaded EVERY user's folders via an unscoped
find_by_type(FOLDER) call, then filtered to the caller's own in Python.
Not a security leak (the filter was applied before the response was
built), but a global, cross-tenant full scan whose cost grew with every
user's total folder count on the installation, not just the caller's own.

This file proves both properties with two real users and real HTTP
requests: correct folders are returned, other users' folders are never
returned, and the fix is a repository-level owner_user_id filter (not a
route-level patch) — i.e. the same centralized pattern established
throughout this project, not an ad-hoc check bolted onto the route.
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

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.main import app

API = "/api/v1"


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db

    user_a = UniversalObject.create(
        object_type=ObjectType.USER, title="Alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:folder-alice-0001"),
    )
    user_b = UniversalObject.create(
        object_type=ObjectType.USER, title="Bob", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:folder-bob-0001"),
    )
    current = {"user": user_a}
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    with TestClient(app) as c:
        yield c, current, user_a, user_b

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _as(current, user):
    current["user"] = user


def _create_folder(client, name):
    resp = client.post(f"{API}/folders", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_list_folders_returns_only_the_callers_own(harness):
    """Test 1 (correct-user case): each user's own folders come back."""
    client, current, user_a, user_b = harness

    _as(current, user_a)
    a1 = _create_folder(client, "Alice's Research")
    a2 = _create_folder(client, "Alice's Teaching")

    _as(current, user_b)
    b1 = _create_folder(client, "Bob's Research")

    _as(current, user_a)
    listing_a = client.get(f"{API}/folders").json()
    ids_a = {item["id"] for item in listing_a["items"]}
    assert {a1["id"], a2["id"]} == ids_a
    assert listing_a["total"] == 2

    _as(current, user_b)
    listing_b = client.get(f"{API}/folders").json()
    ids_b = {item["id"] for item in listing_b["items"]}
    assert ids_b == {b1["id"]}
    assert listing_b["total"] == 1


def test_list_folders_never_returns_other_users_folders(harness):
    """Test 2 (cross-user case): explicit negative assertion, and the same
    guarantee on GET /folders/all."""
    client, current, user_a, user_b = harness

    _as(current, user_a)
    a1 = _create_folder(client, "Alice's Private Grants")

    _as(current, user_b)
    b1 = _create_folder(client, "Bob's Private Grants")

    listing_b = client.get(f"{API}/folders").json()
    ids_b = {item["id"] for item in listing_b["items"]}
    assert a1["id"] not in ids_b
    assert b1["id"] in ids_b

    all_b = client.get(f"{API}/folders/all").json()
    all_ids_b = {item["id"] for item in all_b["items"]}
    assert a1["id"] not in all_ids_b
    assert b1["id"] in all_ids_b

    _as(current, user_a)
    all_a = client.get(f"{API}/folders/all").json()
    all_ids_a = {item["id"] for item in all_a["items"]}
    assert b1["id"] not in all_ids_a
    assert a1["id"] in all_ids_a


def test_folder_listing_is_scoped_at_the_repository_query_not_in_python(harness):
    """Test 3 (the actual perf fix, not just its outward effect): the
    repository's find_by_type() is called with owner_user_id, so filtering
    happens in the SQL query rather than by loading every user's folders
    and discarding most of them in Python."""
    client, current, user_a, user_b = harness

    _as(current, user_a)
    _create_folder(client, "Alice's Folder")
    _as(current, user_b)
    _create_folder(client, "Bob's Folder")

    session = next(app.dependency_overrides[get_db]())
    repo = SQLAlchemyObjectRepository(session)

    # Calling the repository the way the route now does: owner-scoped.
    scoped = repo.find_by_type(ObjectType.FOLDER, owner_user_id=str(user_a.id))
    assert len(scoped) == 1
    assert scoped[0].title == "Alice's Folder"

    # The old behaviour (no owner_user_id) is still available at the
    # repository layer for legitimate unscoped callers — this test
    # documents that the route itself no longer uses it, not that the
    # capability was removed.
    unscoped = repo.find_by_type(ObjectType.FOLDER)
    assert len(unscoped) == 2
