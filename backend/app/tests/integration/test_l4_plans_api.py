"""L4 plans API integration tests (ADR-022/035)."""

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
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:planner-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def test_plans_route_present(client: TestClient):
    # POST /plans with no AI provider configured -> planner unavailable ->
    # deterministic clarify/refuse outcome (never 500, never rules-v1).
    r = client.post(f"{API}/plans", json={"question": "list publications"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["outcome"] in ("execute", "clarify", "refuse")


def test_plans_validate_route(client: TestClient):
    r = client.post(f"{API}/plans/validate", json={"question": "how many grants?"})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] in ("execute", "refuse")
