"""Integration tests: M28 SMART_LINK proposal flow over HTTP.

Full lifecycle over the real app + TestClient (SQLite):

  propose (POST /objects/{id}/links/propose) -> list -> approve -> graph
  traversal shows the promoted edge with ASSERTED provenance; reject path
  removes the edge; ACL (denied user 403 on propose/approve/proposals,
  anonymous 401); candidates the principal cannot READ are never proposed;
  a second propose for a decided target creates nothing.
"""
from __future__ import annotations

import json

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
from app.domain.value_objects.enums import ObjectStatus, ObjectType, Provenance, RelationshipKind
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
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

    current = {}

    def _fake_user():
        from app.core.exceptions import UnauthorizedError

        if current.get("user") is None:
            raise UnauthorizedError("Missing bearer token")
        return current["user"]

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _fake_user

    user_a = UniversalObject.create(
        ObjectType.USER, "owner.a", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:link-a-0001"),
    )
    user_b = UniversalObject.create(
        ObjectType.USER, "denied.b", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:link-b-0002"),
    )

    def set_user(user):
        current["user"] = user

    with TestClient(app) as client:
        yield _Harness(
            client=client, session=session, user_a=user_a, user_b=user_b,
            set_user=set_user,
        )

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class _Harness:
    def __init__(self, *, client, session, user_a, user_b, set_user):
        self.client = client
        self.session = session
        self.user_a = user_a
        self.user_b = user_b
        self.set_user = set_user

    def create(self, object_type, title, metadata=None, *, as_user=None):
        self.set_user(as_user or self.user_a)
        resp = self.client.post(
            f"{API}/objects",
            json={
                "object_type": object_type,
                "title": title,
                "created_by": str((as_user or self.user_a).id),
                "status": "active",
                "metadata": [
                    {"key": k, "value": v, "layer": 6, "source": "asserted"}
                    for k, v in (metadata or {}).items()
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def relationships_of(self, object_id: str):
        repo = SQLAlchemyObjectRepository(self.session)
        obj = repo.get_by_id(ObjectId(object_id))
        return list(obj.relationships) if obj else []


def test_full_flow_propose_approve_traverse(harness):
    pub = harness.create(
        "publication", "Quantum Paper",
        {"authors": "Alice;Bob", "keywords": "quantum"},
    )
    fac = harness.create("faculty", "Alice", {"name": "Alice"})

    # 1. propose
    resp = harness.client.post(f"{API}/objects/{pub}/links/propose")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] == 1
    proposal = body["items"][0]
    assert proposal["target_id"] == fac
    assert proposal["kind"] == "authored_by"
    assert proposal["status"] == "pending"
    assert proposal["confidence"] > 0.0
    assert any("authors" in e for e in proposal["evidence"])

    # the edge is SMART_LINK + INFERRED
    rels = harness.relationships_of(pub)
    smart = [r for r in rels if r.kind is RelationshipKind.SMART_LINK]
    assert len(smart) == 1
    assert smart[0].provenance is Provenance.INFERRED

    # 2. list
    resp = harness.client.get(f"{API}/objects/{pub}/links/proposals")
    assert resp.status_code == 200
    assert [p["target_id"] for p in resp.json()["items"]] == [fac]

    # 3. approve (human reviewer)
    resp = harness.client.post(f"{API}/objects/{pub}/links/{fac}/approve")
    assert resp.status_code == 200, resp.text
    decision = resp.json()
    assert decision["status"] == "approved"
    assert decision["kind"] == "authored_by"

    # edge promoted: ASSERTED authored_by, SMART_LINK gone
    rels = harness.relationships_of(pub)
    assert all(r.kind is not RelationshipKind.SMART_LINK for r in rels)
    promoted = [r for r in rels if r.kind is RelationshipKind.AUTHORED_BY]
    assert len(promoted) == 1
    assert promoted[0].provenance is Provenance.ASSERTED

    # 4. graph traversal sees the neighbor (approved edge is live)
    resp = harness.client.get(f"{API}/objects/{pub}/graph?depth=1")
    assert resp.status_code == 200
    assert any(item["id"] == fac for item in resp.json()["items"])

    # 5. re-propose for the decided target creates nothing
    resp = harness.client.post(f"{API}/objects/{pub}/links/propose")
    assert resp.status_code == 201
    assert resp.json()["created"] == 0

    # 6. double approve -> 409
    resp = harness.client.post(f"{API}/objects/{pub}/links/{fac}/approve")
    assert resp.status_code == 409, resp.text


def test_full_flow_propose_reject_removes_edge(harness):
    pub = harness.create(
        "publication", "Paper B", {"authors": "Carol", "keywords": "ml"},
    )
    fac = harness.create("faculty", "Carol", {"name": "Carol"})

    resp = harness.client.post(f"{API}/objects/{pub}/links/propose")
    assert resp.json()["created"] == 1

    resp = harness.client.post(f"{API}/objects/{pub}/links/{fac}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["kind"] == ""

    rels = harness.relationships_of(pub)
    assert all(r.kind is not RelationshipKind.SMART_LINK for r in rels)

    resp = harness.client.post(f"{API}/objects/{pub}/links/{fac}/reject")
    assert resp.status_code == 409  # no pending proposal


def test_acl_denied_user_cannot_propose_review_or_list(harness):
    pub = harness.create("publication", "Locked Paper", {"authors": "Alice"})
    # Restrict the publication to user A only.
    acl = harness.client.put(
        f"{API}/objects/{pub}/acl",
        json={
            "readers": [str(harness.user_a.id)],
            "writers": [str(harness.user_a.id)],
            "managers": [str(harness.user_a.id)],
        },
    )
    assert acl.status_code == 200, acl.text

    harness.set_user(harness.user_b)
    assert harness.client.post(f"{API}/objects/{pub}/links/propose").status_code == 403
    assert harness.client.get(f"{API}/objects/{pub}/links/proposals").status_code == 403
    assert harness.client.post(
        f"{API}/objects/{pub}/links/obj:faculty:0000000000000001/approve"
    ).status_code == 403
    harness.set_user(None)
    assert harness.client.get(f"{API}/objects/{pub}/links/proposals").status_code == 401


def test_propose_skips_candidates_the_principal_cannot_read(harness):
    pub = harness.create("publication", "Pub C", {"authors": "Dave"})
    other = harness.create("faculty", "Dave", {"name": "Dave"}, as_user=harness.user_b)
    # Lock the faculty object to user B only — user A cannot read it.
    acl = harness.client.put(
        f"{API}/objects/{other}/acl",
        json={
            "readers": [str(harness.user_b.id)],
            "writers": [str(harness.user_b.id)],
            "managers": [str(harness.user_b.id)],
        },
    )
    assert acl.status_code == 200, acl.text

    # User A proposes on their publication: the locked faculty is skipped.
    harness.set_user(harness.user_a)
    resp = harness.client.post(f"{API}/objects/{pub}/links/propose")
    assert resp.status_code == 201
    assert resp.json()["created"] == 0
    assert resp.json()["items"] == []


def test_approve_requires_write_on_target(harness):
    pub = harness.create("publication", "Pub D", {"authors": "Eve"})
    other = harness.create("faculty", "Eve", {"name": "Eve"}, as_user=harness.user_b)
    harness.set_user(harness.user_a)
    resp = harness.client.post(f"{API}/objects/{pub}/links/propose")
    assert resp.json()["created"] == 1

    # Owner (user B) locks the faculty — user A cannot WRITE the target.
    harness.set_user(harness.user_b)
    acl = harness.client.put(
        f"{API}/objects/{other}/acl",
        json={
            "readers": [str(harness.user_b.id)],
            "writers": [str(harness.user_b.id)],
            "managers": [str(harness.user_b.id)],
        },
    )
    assert acl.status_code == 200, acl.text
    harness.set_user(harness.user_a)
    resp = harness.client.post(f"{API}/objects/{pub}/links/{other}/approve")
    assert resp.status_code == 403, resp.text


def test_unknown_ids_map_to_404_and_422(harness):
    harness.set_user(harness.user_a)
    resp = harness.client.post(
        f"{API}/objects/obj:publication:0000000000000001/links/propose"
    )
    assert resp.status_code == 404
    resp = harness.client.post(f"{API}/objects/not-an-id/links/propose")
    assert resp.status_code == 422
