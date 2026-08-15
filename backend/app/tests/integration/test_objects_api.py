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
from app.domain.value_objects.object_id import ObjectId
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
        object_id=ObjectId("obj:user:test-user-0001"),
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


# ------------------------------------------------- Sprint-2 M1 — object ACL + graph


def _register_login(client, username, password="pass-word-123"):
    client.post("/api/v1/auth/register", json={"username": username, "password": password})
    return client.post("/api/v1/auth/login", json={"username": username, "password": password}).json()[
        "access_token"
    ]


def _use_real_tokens():
    """These tests exercise object ACL with real accounts, so the fixture's
    fake-user override of get_current_user must be lifted."""
    app.dependency_overrides.pop(get_current_user, None)



def test_object_acl_grants_and_enforces(client):
    _use_real_tokens()
    owner_token = _register_login(client, "acl.owner")
    insider_token = _register_login(client, "acl.insider")
    stranger_token = _register_login(client, "acl.stranger")

    created = client.post(
        "/api/v1/objects",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"object_type": "course", "title": "ACL Course", "created_by": "x", "status": "draft"},
    )
    assert created.status_code == 201
    oid = created.json()["id"]

    # Before any ACL: everyone can read (status quo).
    assert (
        client.get(f"/api/v1/objects/{oid}", headers={"Authorization": f"Bearer {stranger_token}"}).status_code
        == 200
    )

    # Owner grants READ to the insider.
    acl_resp = client.put(
        f"/api/v1/objects/{oid}/acl",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"readers": [client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {insider_token}"}).json()["id"]], "writers": [], "managers": []},
    )
    assert acl_resp.status_code == 200
    assert acl_resp.json()["readers"]

    # Stranger now denied (403); insider allowed (200).
    assert (
        client.get(f"/api/v1/objects/{oid}", headers={"Authorization": f"Bearer {stranger_token}"}).status_code
        == 403
    )
    assert (
        client.get(f"/api/v1/objects/{oid}", headers={"Authorization": f"Bearer {insider_token}"}).status_code
        == 200
    )
    # Insider is READ-only: update -> 403; owner update -> 200.
    assert (
        client.put(
            f"/api/v1/objects/{oid}",
            headers={"Authorization": f"Bearer {insider_token}"},
            json={"updated_by": "x", "status": "active"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/objects/{oid}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"updated_by": "x", "status": "active"},
        ).status_code
        == 200
    )
    # Delete is MANAGE: stranger/insider 403, owner 204.
    assert (
        client.delete(f"/api/v1/objects/{oid}", headers={"Authorization": f"Bearer {stranger_token}"}).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/objects/{oid}", headers={"Authorization": f"Bearer {owner_token}"}).status_code
        == 204
    )


def test_acl_write_requires_manage_and_validates(client):
    _use_real_tokens()
    owner_token = _register_login(client, "acl.owner2")
    stranger_token = _register_login(client, "acl.stranger2")
    created = client.post(
        "/api/v1/objects",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"object_type": "course", "title": "ACL2", "created_by": "x", "status": "draft"},
    ).json()
    oid = created["id"]

    # A stranger cannot write the ACL.
    assert (
        client.put(
            f"/api/v1/objects/{oid}/acl",
            headers={"Authorization": f"Bearer {stranger_token}"},
            json={"readers": ["obj:user:X"], "writers": [], "managers": []},
        ).status_code
        == 403
    )
    # Unknown role entries are rejected (422).
    assert (
        client.put(
            f"/api/v1/objects/{oid}/acl",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"readers": ["role:superuser"], "writers": [], "managers": []},
        ).status_code
        == 422
    )
    # Generic metadata cannot forge an ACL.
    assert (
        client.put(
            f"/api/v1/objects/{oid}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"updated_by": "x", "metadata": [{"key": "acl.readers", "value": '["obj:user:X"]'}]},
        ).status_code
        == 422
    )


def test_object_graph_traversal_with_acl_filtering(client):
    _use_real_tokens()
    owner_token = _register_login(client, "graph.owner")
    outsider_token = _register_login(client, "graph.outsider")
    H = {"Authorization": f"Bearer {owner_token}"}

    a = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "G-A", "created_by": "x", "status": "draft"}).json()["id"]
    b = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "G-B", "created_by": "x", "status": "draft"}).json()["id"]
    c = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "G-C", "created_by": "x", "status": "draft"}).json()["id"]

    # Seed edges directly through the repository (the graph surface).
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )
    from app.domain.value_objects.enums import RelationshipKind, Provenance

    session = next(app.dependency_overrides[get_db]())
    repo = SQLAlchemyObjectRepository(session)
    for source, target in ((a, b), (a, c), (c, a)):
        obj = repo.get_by_id(__import__("app.domain.value_objects.object_id", fromlist=["ObjectId"]).ObjectId(source))
        obj.add_relationship(
            __import__("app.domain.value_objects.object_id", fromlist=["ObjectId"]).ObjectId(target),
            RelationshipKind.PREREQUISITE_OF,
            Provenance.ASSERTED,
        )
        repo.save(obj)

    # Owner sees the full outgoing graph.
    graph = client.get(f"/api/v1/objects/{a}/graph", headers=H)
    assert graph.status_code == 200
    assert {i["id"] for i in graph.json()["items"]} == {b, c}
    # Incoming: C is referenced by A; A is referenced by C.
    incoming = client.get(f"/api/v1/objects/{c}/graph?direction=incoming", headers=H)
    assert {i["id"] for i in incoming.json()["items"]} == {a}

    # Grant B to a third party; the outsider's traversal of A must not leak
    # B, while the grantee sees it.
    grantee_token = _register_login(client, "graph.grantee")
    grantee_id = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {grantee_token}"}).json()["id"]
    client.put(
        f"/api/v1/objects/{b}/acl",
        headers=H,
        json={"readers": [grantee_id], "writers": [], "managers": []},
    )
    outsider_graph = client.get(
        f"/api/v1/objects/{a}/graph", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert outsider_graph.status_code == 200
    assert {i["id"] for i in outsider_graph.json()["items"]} == {c}  # B filtered out

    grantee_graph = client.get(
        f"/api/v1/objects/{a}/graph", headers={"Authorization": f"Bearer {grantee_token}"}
    )
    assert grantee_graph.status_code == 200
    assert {i["id"] for i in grantee_graph.json()["items"]} == {b, c}  # B visible to its grantee


def test_graph_runtime_depth_cycles_and_path(client):
    """S2 M2 — multi-hop traversal, cycle detection and shortest path over HTTP."""
    owner_token = _register_login(client, "runtime.owner")
    H = {"Authorization": f"Bearer {owner_token}"}

    a = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "R-A", "created_by": "x", "status": "draft"}).json()["id"]
    b = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "R-B", "created_by": "x", "status": "draft"}).json()["id"]
    c = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "R-C", "created_by": "x", "status": "draft"}).json()["id"]

    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )
    from app.domain.value_objects.enums import RelationshipKind, Provenance
    from app.domain.value_objects.object_id import ObjectId

    session = next(app.dependency_overrides[get_db]())
    repo = SQLAlchemyObjectRepository(session)
    for source, target in ((a, b), (b, c), (c, a)):  # cycle A->B->C->A
        obj = repo.get_by_id(ObjectId(source))
        obj.add_relationship(ObjectId(target), RelationshipKind.PREREQUISITE_OF, Provenance.ASSERTED)
        repo.save(obj)

    # Depth-3 BFS reaches B and C and expands C, completing the cycle walk
    # A->B->C->A — the cycle is detected inside the traversed subgraph.
    out = client.get(f"/api/v1/objects/{a}/graph?depth=3", headers=H)
    assert out.status_code == 200
    body = out.json()
    assert {i["id"] for i in body["items"]} == {b, c}
    assert body["has_cycle"] is True
    assert body["total_count"] == 2
    # Item shape is additive: title + level present.
    by_id = {i["id"]: i for i in body["items"]}
    assert by_id[b]["title"] == "R-B" and by_id[b]["level"] == 1
    assert by_id[c]["level"] == 2

    # DFS mode reaches the same nodes (cycle requires depth 3 to close).
    dfs = client.get(f"/api/v1/objects/{a}/graph?depth=3&mode=dfs", headers=H)
    assert {i["id"] for i in dfs.json()["items"]} == {b, c}

    # Shortest path A -> C is A->B->C (2 hops).
    path = client.get(f"/api/v1/objects/{a}/graph/path?target={c}&max_hops=3", headers=H)
    assert path.status_code == 200
    body = path.json()
    assert body["found"] is True
    assert body["path"] == [a, b, c]
    assert body["hops"] == 2

    # Hop limit excludes the route.
    short = client.get(f"/api/v1/objects/{a}/graph/path?target={c}&max_hops=1", headers=H)
    assert short.json()["found"] is False

    # Bad params are 422.
    assert client.get(f"/api/v1/objects/{a}/graph?depth=9", headers=H).status_code == 422
    assert client.get(f"/api/v1/objects/{a}/graph/path?target={c}&max_hops=9", headers=H).status_code == 422


def test_delete_referenced_object_rejected(client):
    """S2 M3 — hard delete must not orphan inbound edges: deleting an
    object that others reference is rejected with 422."""
    owner_token = _register_login(client, "integrity.owner")
    H = {"Authorization": f"Bearer {owner_token}"}

    a = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "I-A", "created_by": "x", "status": "draft"}).json()["id"]
    b = client.post("/api/v1/objects", headers=H, json={"object_type": "course", "title": "I-B", "created_by": "x", "status": "draft"}).json()["id"]

    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )
    from app.domain.value_objects.enums import RelationshipKind, Provenance
    from app.domain.value_objects.object_id import ObjectId

    session = next(app.dependency_overrides[get_db]())
    repo = SQLAlchemyObjectRepository(session)
    a_obj = repo.get_by_id(ObjectId(a))
    a_obj.add_relationship(ObjectId(b), RelationshipKind.PREREQUISITE_OF, Provenance.ASSERTED)
    repo.save(a_obj)

    # A references B, so deleting B is refused.
    assert (
        client.delete(f"/api/v1/objects/{b}", headers=H).status_code
        == 422
    )
    # Deleting A (which nothing references) works.
    assert client.delete(f"/api/v1/objects/{a}", headers=H).status_code == 204
    # After A is gone, B is deletable.
    assert client.delete(f"/api/v1/objects/{b}", headers=H).status_code == 204
