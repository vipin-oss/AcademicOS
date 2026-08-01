"""Smoke test for the health endpoint (no external services required)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_root_responds() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "AcademicOS"


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "academicos-api"
