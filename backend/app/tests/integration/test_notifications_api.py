"""Integration tests for the Notification API.

Tests the full HTTP endpoints for notifications.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.models.notification_model import Base
from app.infrastructure.db.models.object_model import ObjectModel
from app.main import app
from app.infrastructure.db.session import get_db


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    ObjectModel.__table__.create(engine, checkfirst=True)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    """Create a test user and return auth headers."""
    # For testing, we'll create a minimal user object
    return {"Authorization": "Bearer test-token"}


def test_notification_endpoints_exist(client):
    """Verify notification routes are registered."""
    # This just tests that the routes exist (401 without auth)
    res = client.get("/api/v1/notifications")
    assert res.status_code in (401, 403)


def test_notification_count_endpoint_exists(client):
    """Verify notification count route exists."""
    res = client.get("/api/v1/notifications/count")
    assert res.status_code in (401, 403)


def test_notification_mark_read_endpoint_exists(client):
    """Verify mark-read route exists."""
    res = client.put("/api/v1/notifications/test-id/read")
    assert res.status_code in (401, 403)


def test_notification_read_all_endpoint_exists(client):
    """Verify mark-all-read route exists."""
    res = client.put("/api/v1/notifications/read-all")
    assert res.status_code in (401, 403)


def test_notification_delete_endpoint_exists(client):
    """Verify delete route exists."""
    res = client.delete("/api/v1/notifications/test-id")
    assert res.status_code in (401, 403)
