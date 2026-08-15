"""L5 tools API integration tests (ADR-022/037)."""

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
from app.infrastructure.db.models.tool_call_log_model import ToolCallLogModel  # noqa: F401
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

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="test.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:l5-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def test_list_tools(client: TestClient):
    r = client.get(f"{API}/tools")
    assert r.status_code == 200, r.text
    names = [t["name"] for t in r.json()]
    assert "inventory" in names and "count" in names and "list" in names and "lookup" in names


def test_invoke_count_tool(client: TestClient):
    r = client.post(f"{API}/tools/count/invoke", json={"args": {"object_type": "publication"}})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert isinstance(r.json()["value"]["count"], int)


def test_invoke_unknown_tool(client: TestClient):
    r = client.post(f"{API}/tools/nope/invoke", json={"args": {}})
    assert r.status_code == 400


def test_invoke_invalid_input(client: TestClient):
    r = client.post(f"{API}/tools/count/invoke", json={"args": {"object_type": 5}})
    assert r.status_code == 400


def test_tool_calls_audit(client: TestClient):
    client.post(f"{API}/tools/count/invoke", json={"args": {"object_type": "publication"}})
    r = client.get(f"{API}/tools/calls")
    assert r.status_code == 200
    # audit log recorded at least one tool call for principal l5-0001
    assert any(c["principal"] == "obj:user:l5-0001" for c in r.json())
