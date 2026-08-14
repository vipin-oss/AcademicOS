"""L7 integration tests — persistent memory API (ADR-041)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa: F401
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="test.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:l7a-0001"),
    )
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    # persist the user via the repository (not the ORM directly)
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    SQLAlchemyObjectRepository(session).save(fake_user)
    session.commit()

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


API = "/api/v1"


def test_write_and_list_memory(client: TestClient):
    r = client.post(
        f"{API}/assistant/memory",
        json={"question": "What is the budget?", "answer": "5000000", "provenance": "asserted"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["artifact_id"].startswith("obj:memory_artifact:")
    assert body["review_status"] == "approved"

    lst = client.get(f"{API}/assistant/memory")
    assert lst.status_code == 200, lst.text
    artifacts = lst.json()["artifacts"]
    assert any(a["artifact_id"] == body["artifact_id"] for a in artifacts)


def test_write_system_memory_pending_review_gate(client: TestClient):
    r = client.post(
        f"{API}/assistant/memory",
        json={"question": "auto note", "answer": "x", "provenance": "system"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["review_status"] == "pending"


def test_forget_memory(client: TestClient):
    r = client.post(
        f"{API}/assistant/memory",
        json={"question": "temp", "answer": "data", "provenance": "asserted"},
    )
    aid = r.json()["artifact_id"]
    d = client.delete(f"{API}/assistant/memory/{aid}")
    assert d.status_code == 200, d.text
    assert d.json()["status"] == "superseded"
