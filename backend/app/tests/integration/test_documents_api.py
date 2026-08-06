"""Integration tests for the Documents API (Phase 2 CRUD slice).

Skipped automatically when FastAPI / SQLAlchemy / pydantic-settings are not
installed. Uses an in-memory SQLite database plus a temporary local storage
root so the slice is verifiable end-to-end in CI without PostgreSQL or disk
state — mirrors ``test_objects_api.py``.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.api.dependencies.auth import get_current_user

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.routes.documents import get_storage
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    storage = LocalFileStorage(str(tmp_path / "storage"))

    def _override_db():
        yield session

    def _override_storage():
        return storage

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_storage] = _override_storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _create_object(client, **kwargs):
    defaults = {
        "object_type": "course",
        "title": "Intro to CS",
        "created_by": "faculty:1",
    }
    defaults.update(kwargs)
    return client.post("/api/v1/objects", json=defaults)


def _upload(client, **kwargs):
    data = {
        "title": "CS101 Syllabus",
        "document_type": "pdf",
        "uploaded_by": "faculty:1",
        "description": "Course syllabus",
        "tags": '["syllabus", "fall-2026"]',
    }
    files = {"file": ("syllabus.pdf", b"%PDF-sample-bytes", "application/pdf")}
    data.update(kwargs.pop("data", {}))
    return client.post("/api/v1/documents", data=data, files=files, **kwargs)


def test_upload_then_get_document(client):
    resp = _upload(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("obj:document:")
    assert body["title"] == "CS101 Syllabus"
    assert body["document_type"] == "pdf"
    assert body["description"] == "Course syllabus"
    assert body["tags"] == ["syllabus", "fall-2026"]
    assert body["file_name"] == "syllabus.pdf"
    assert body["file_size"] == len(b"%PDF-sample-bytes")
    assert body["mime_type"] == "application/pdf"
    assert body["status"] == "draft"
    assert body["uploaded_by"] == "faculty:1"
    assert body["object_id"] is None
    assert body["url"] is not None  # stored blob -> working download link

    got = client.get(f"/api/v1/documents/{body['id']}")
    assert got.status_code == 200
    assert got.json()["title"] == "CS101 Syllabus"


def test_upload_validation_errors(client):
    # invalid document_type -> 422
    resp = _upload(client, data={"document_type": "bogus"})
    assert resp.status_code == 422
    # invalid tags payload -> 422
    resp = _upload(client, data={"tags": "not-json"})
    assert resp.status_code == 422
    # missing title -> 422 (FastAPI form validation)
    resp = client.post(
        "/api/v1/documents",
        data={"document_type": "pdf", "uploaded_by": "faculty:1"},
        files={"file": ("a.pdf", b"x", "application/pdf")},
    )
    assert resp.status_code == 422
    # link to a non-existent object -> 422
    resp = _upload(client, data={"object_id": "obj:course:NOPE"})
    assert resp.status_code == 422


def test_download_round_trip(client):
    body = _upload(client).json()
    resp = client.get(f"/api/v1/documents/{body['id']}/download")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-sample-bytes"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "syllabus.pdf" in resp.headers["content-disposition"]


def test_list_pagination(client):
    for i in range(5):
        _upload(client, data={"title": f"Doc {i}"})
    resp = client.get("/api/v1/documents", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 5
    assert len(body["items"]) == 2

    resp2 = client.get("/api/v1/documents", params={"page": 3, "page_size": 2})
    assert len(resp2.json()["items"]) == 1

    bad = client.get("/api/v1/documents", params={"page": 0, "page_size": 20})
    assert bad.status_code == 422


def test_object_document_linking(client):
    course = _create_object(client).json()
    body = _upload(client, data={"object_id": course["id"]}).json()
    assert body["object_id"] == course["id"]
    assert body["object_title"] == "Intro to CS"
    assert body["object_type"] == "course"

    # The Object-detail-page query: GET /documents?object_id=…
    linked = client.get("/api/v1/documents", params={"object_id": course["id"], "page_size": 100})
    assert linked.status_code == 200
    ids = [item["id"] for item in linked.json()["items"]]
    assert ids == [body["id"]]

    # Object-centric model: a Document IS an Object, so it also appears in the
    # generic Objects explorer as object_type=document (frozen behaviour).
    objects = client.get("/api/v1/objects", params={"page_size": 100}).json()
    doc_rows = [item for item in objects["items"] if item["id"] == body["id"]]
    assert len(doc_rows) == 1
    assert doc_rows[0]["object_type"] == "document"


def test_update_document_via_put_and_patch(client):
    body = _upload(client).json()

    resp = client.put(
        f"/api/v1/documents/{body['id']}",
        json={
            "title": "CS101 Syllabus v2",
            "description": "Updated",
            "tags": ["syllabus"],
            "status": "active",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["title"] == "CS101 Syllabus v2"
    assert updated["status"] == "active"
    assert updated["description"] == "Updated"
    assert updated["tags"] == ["syllabus"]
    assert updated["version"] > body["version"]
    assert updated["updated_at"] is not None

    # PATCH behaves identically (same handler).
    resp = client.patch(
        f"/api/v1/documents/{body['id']}", json={"title": "CS101 Syllabus v3"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "CS101 Syllabus v3"


def test_update_document_link_unlink(client):
    course = _create_object(client).json()
    body = _upload(client).json()

    linked = client.put(
        f"/api/v1/documents/{body['id']}", json={"object_id": course["id"]}
    )
    assert linked.status_code == 200
    assert linked.json()["object_id"] == course["id"]

    unlinked = client.put(f"/api/v1/documents/{body['id']}", json={"object_id": None})
    assert unlinked.status_code == 200
    assert unlinked.json()["object_id"] is None

    bad = client.put(
        f"/api/v1/documents/{body['id']}", json={"object_id": "obj:course:NOPE"}
    )
    assert bad.status_code == 422


def test_update_invalid_transition_returns_422(client):
    body = _upload(client).json()
    client.put(f"/api/v1/documents/{body['id']}", json={"status": "archived"})
    # archived -> draft is rejected by the domain lifecycle rules.
    resp = client.put(f"/api/v1/documents/{body['id']}", json={"status": "draft"})
    assert resp.status_code == 422


def test_update_missing_document_returns_404(client):
    resp = client.put(
        "/api/v1/documents/obj:document:NOPE", json={"title": "Nope"}
    )
    assert resp.status_code == 404


def test_get_missing_document_returns_404(client):
    assert client.get("/api/v1/documents/obj:document:NOPE").status_code == 404
    # An existing non-document Object is not a Document.
    course = _create_object(client).json()
    assert client.get(f"/api/v1/documents/{course['id']}").status_code == 404


def test_delete_document(client):
    body = _upload(client).json()
    resp = client.delete(f"/api/v1/documents/{body['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/documents/{body['id']}").status_code == 404
    assert client.delete(f"/api/v1/documents/{body['id']}").status_code == 404
