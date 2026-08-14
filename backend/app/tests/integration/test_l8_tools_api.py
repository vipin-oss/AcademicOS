"""L8 tools API integration tests (ADR-022/037/043)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.tool_call_log_model import ToolCallLogModel  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="u:1", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:l8-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    repo.save(fake_user)
    # seed a grant for cross-domain invocation
    grant = UniversalObject.create(
        ObjectType.GRANT, "HSRF Grant", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:grant:l8a-1"),
    )
    repo.save(grant)
    session.commit()
    with TestClient(app) as c:
        yield c, repo, grant
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


API = "/api/v1"


def test_list_tools_includes_l8(client):
    c, _repo, _grant = client
    r = c.get(f"{API}/tools")
    assert r.status_code == 200, r.text
    names = [t["name"] for t in r.json()]
    for name in ("cross-domain", "absence", "temporal", "compare"):
        assert name in names, f"missing L8 tool {name}"
    # L5 base tools still present (additive, not replaced)
    for name in ("inventory", "count", "list", "lookup"):
        assert name in names


def test_invoke_cross_domain_tool(client):
    c, _repo, grant = client
    r = c.post(
        f"{API}/tools/cross-domain/invoke",
        json={"args": {"entities": [str(grant.id)], "depth": 2}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["value"]["total_count"] >= 1


def test_invoke_absence_tool(client):
    c, _repo, _grant = client
    r = c.post(
        f"{API}/tools/absence/invoke",
        json={"args": {"object_type": "course"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["value"]["outcome"] in ("confirmed_absence", "present", "insufficient_evidence")
