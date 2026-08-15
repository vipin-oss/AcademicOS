"""Integration tests for the document viewer API (Sprint M10).

Full TestClient surface: annotation CRUD (create/list/update/delete),
the 401 gate, 404s for unknown documents/annotations, validation 422s,
and the extracted-text endpoint resolving a document's linked intake
item (seeded the way the M9 Commit Engine links them).
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.dependencies.auth import get_current_user  # noqa: E402
from app.api.routes.documents import get_storage  # noqa: E402
from app.domain.entities.object import UniversalObject  # noqa: E402
from app.domain.value_objects.enums import (  # noqa: E402
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry  # noqa: E402
from app.domain.value_objects.object_id import ObjectId  # noqa: E402
from app.infrastructure.db.models.annotation_model import (  # noqa: E402,F401
    DocumentAnnotationModel,
)
from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.infrastructure.repositories.sqlalchemy_object_repository import (  # noqa: E402
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1/documents"


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="test.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    storage = LocalFileStorage(str(tmp_path / "storage"))
    app.dependency_overrides[get_storage] = lambda: storage
    repo = SQLAlchemyObjectRepository(session)
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "paper.pdf", created_by="test.user",
        status=ObjectStatus.ACTIVE,
    )
    doc.pop_domain_events()
    repo.save(doc)
    with TestClient(app) as client:
        yield client, repo, storage, doc
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


# ------------------------------------------------------------------ auth
def test_viewer_endpoints_require_authentication(harness):
    client, _, _, doc = harness
    app.dependency_overrides.pop(get_current_user, None)
    try:
        assert client.get(f"{API}/{doc.id}/annotations").status_code == 401
        assert client.post(
            f"{API}/{doc.id}/annotations",
            json={"annotation_type": "note", "page": 1, "payload": {"text": "x"}},
        ).status_code == 401
        assert client.get(f"{API}/{doc.id}/extracted-text").status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: UniversalObject.create(
            object_type=ObjectType.USER, title="test.user", created_by="system",
            status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:test-user-0001"),
        )


# ------------------------------------------------------------- annotations
def test_annotation_crud_round_trip(harness):
    client, _, _, doc = harness
    r = client.post(
        f"{API}/{doc.id}/annotations",
        json={
            "annotation_type": "highlight",
            "page": 1,
            "payload": {"rects": [{"x0": 0, "y0": 0, "x1": 9, "y1": 9}], "text": "wave"},
        },
    )
    assert r.status_code == 201, r.text
    annotation = r.json()
    assert annotation["annotation_type"] == "highlight"
    assert annotation["page"] == 1
    assert annotation["document_id"] == str(doc.id)
    assert annotation["created_by"] == "obj:user:test-user-0001"

    listed = client.get(f"{API}/{doc.id}/annotations").json()["items"]
    assert [a["annotation_id"] for a in listed] == [annotation["annotation_id"]]

    updated = client.put(
        f"{API}/annotations/{annotation['annotation_id']}",
        json={"page": 2, "payload": {"rects": [], "text": "waves"}},
    )
    assert updated.status_code == 200
    assert updated.json()["page"] == 2
    assert updated.json()["updated_at"]

    deleted = client.delete(f"{API}/annotations/{annotation['annotation_id']}")
    assert deleted.status_code == 204
    assert client.get(f"{API}/{doc.id}/annotations").json()["items"] == []


def test_annotation_validation_and_404s(harness):
    client, _, _, doc = harness
    assert client.post(
        f"{API}/{doc.id}/annotations",
        json={"annotation_type": "sticky", "page": 1, "payload": {"x": 1}},
    ).status_code == 422
    assert client.post(
        f"{API}/{doc.id}/annotations",
        json={"annotation_type": "note", "page": 0, "payload": {"text": "x"}},
    ).status_code == 422
    assert client.post(
        f"{API}/{doc.id}/annotations",
        json={"annotation_type": "note", "page": 1, "payload": {}},
    ).status_code == 422
    assert client.post(
        f"{API}/obj:document:missing/annotations",
        json={"annotation_type": "note", "page": 1, "payload": {"text": "x"}},
    ).status_code == 404
    assert client.put(
        f"{API}/annotations/not-there", json={"page": 2}
    ).status_code == 404
    assert client.delete(f"{API}/annotations/not-there").status_code == 404


# --------------------------------------------------------- extracted text
def test_extracted_text_returns_the_linked_item_text(harness):
    client, repo, storage, doc = harness
    session_obj = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "session", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(_entry("intake.status", "completed"),)),
    )
    repo.save(session_obj)
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM, "paper.pdf", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry("intake.status", "committed"),
                _entry("intake.session_id", str(session_obj.id)),
                _entry(
                    "intake.extraction",
                    json.dumps({"status": "extracted", "text_key": "extract/paper.txt"}),
                ),
            )
        ),
    )
    repo.save(item)
    doc.add_relationship(item.id, RelationshipKind.BELONGS_TO, actor="system")
    repo.save(doc)
    storage.save("extract/paper.txt", b"Propagation of waves in piezothermoelastic media")

    r = client.get(f"{API}/{doc.id}/extracted-text")
    assert r.status_code == 200
    body = r.json()
    assert "piezothermoelastic" in body["text"]
    assert body["item_id"] == str(item.id)
    assert body["session_id"] == str(session_obj.id)


def test_extracted_text_404_without_link(harness):
    client, _, _, doc = harness
    assert client.get(f"{API}/{doc.id}/extracted-text").status_code == 404
