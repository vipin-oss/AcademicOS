"""Integration tests for the Objects API (Phase 1 CRUD slice).

Skipped automatically when FastAPI / SQLAlchemy / pydantic-settings are not
installed or when no database is reachable. Uses an in-memory SQLite database so
the slice is verifiable end-to-end in CI without a PostgreSQL server.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.api.dependencies.auth import get_current_user

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.domain.entities.object import UniversalObject
from app.main import app


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
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _create(client, **kwargs):
    defaults = {
        "object_type": "course",
        "title": "Intro to CS",
        "created_by": "faculty:1",
        "metadata": [{"key": "code", "value": "CS101"}],
    }
    defaults.update(kwargs)
    return client.post("/api/v1/objects", json=defaults)


def test_create_then_get_object(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["object_type"] == "course"
    assert body["metadata"] == {"code": "CS101"}

    oid = body["id"]
    got = client.get(f"/api/v1/objects/{oid}")
    assert got.status_code == 200
    assert got.json()["title"] == "Intro to CS"


def test_create_invalid_type_returns_422(client):
    resp = _create(client, object_type="bogus")
    assert resp.status_code == 422


def test_get_missing_object_returns_404(client):
    resp = client.get("/api/v1/objects/obj:course:NOPE")
    assert resp.status_code == 404


def test_list_pagination(client):
    for i in range(5):
        _create(client, title=f"Course {i}")
    resp = client.get("/api/v1/objects", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    resp2 = client.get("/api/v1/objects", params={"page": 3, "page_size": 2})
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 1


def test_list_validation_422(client):
    resp = client.get("/api/v1/objects", params={"page": 0, "page_size": 20})
    assert resp.status_code == 422


def test_update_object(client):
    oid = _create(client).json()["id"]
    resp = client.put(
        f"/api/v1/objects/{oid}",
        json={"updated_by": "faculty:1", "status": "archived", "metadata": [{"key": "note", "value": "x"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"
    assert body["metadata"]["note"] == "x"
    assert body["metadata"]["code"] == "CS101"  # preserved


def test_update_missing_object_returns_404(client):
    resp = client.put(
        "/api/v1/objects/obj:course:NOPE",
        json={"updated_by": "faculty:1", "status": "archived"},
    )
    assert resp.status_code == 404


def test_delete_object(client):
    oid = _create(client).json()["id"]
    resp = client.delete(f"/api/v1/objects/{oid}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/objects/{oid}").status_code == 404


def test_delete_missing_object_returns_404(client):
    resp = client.delete("/api/v1/objects/obj:course:NOPE")
    assert resp.status_code == 404


def test_update_concurrency_conflict_maps_to_409(client):
    """R3 — a refused stale write surfaces as HTTP 409, not a 500."""
    from app.api.routes import objects as objects_route
    from app.domain.entities.object import UniversalObject
    from app.domain.exceptions import OptimisticConcurrencyError
    from app.domain.value_objects.enums import ObjectType

    class ConflictingRepository:
        """A repository whose save() loses to a concurrent writer every time."""

        def get_by_id(self, object_id):
            return UniversalObject.create(
                ObjectType.COURSE, "Raced", created_by="faculty:1"
            )

        def save(self, entity):
            raise OptimisticConcurrencyError(
                f"Object {entity.id} changed since it was loaded (expected version 1)."
            )

    app.dependency_overrides[objects_route._repository] = lambda: ConflictingRepository()
    try:
        resp = client.put(
            "/api/v1/objects/obj:course:RACED",
            json={"updated_by": "faculty:1", "status": "active"},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "optimistic_concurrency_conflict"
        assert "changed since it was loaded" in body["error"]["message"]
    finally:
        app.dependency_overrides.pop(objects_route._repository, None)
