"""V3 M14 admin panel API tests (ADR-061)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.application.use_cases.auth.helpers import set_roles
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.job_model import JobAttemptModel, JobModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.saved_view_model import SavedViewModel  # noqa: F401
from app.infrastructure.db.models.session_revocation_model import (  # noqa: F401
    SessionRevocationModel,
)
from app.infrastructure.db.models.spend_ledger_model import SpendLedgerModel  # noqa: F401
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    def _override_db():
        yield session

    admin = UniversalObject.create(
        ObjectType.USER, "admin", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:admin-0001"),
    )
    set_roles(admin, ["admin"])

    def _override_user():
        return admin

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app) as c:
        yield c, session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def test_admin_jobs_returns_counts(client):
    client, session = client
    r = client.get("/api/v1/admin/jobs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"pending", "running", "retryable", "failed", "succeeded"}


def test_admin_spend_returns_totals(client):
    client, session = client
    r = client.get("/api/v1/admin/spend")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_usd"] == 0.0
    assert body["by_user"] == {}


def test_admin_extraction_health(client):
    client, session = client
    r = client.get("/api/v1/admin/extraction-health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_corrections"] == 0
    assert body["by_predicate"] == {}


def test_non_admin_is_forbidden(client):
    client, session = client
    # override to a non-admin user
    from app.application.use_cases.auth.helpers import set_roles as _sr

    non_admin = UniversalObject.create(
        ObjectType.USER, "prof", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:prof-0001"),
    )
    _sr(non_admin, ["professor"])
    app.dependency_overrides[get_current_user] = lambda: non_admin
    r = client.get("/api/v1/admin/jobs")
    assert r.status_code == 403
