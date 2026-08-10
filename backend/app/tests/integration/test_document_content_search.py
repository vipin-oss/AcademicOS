"""Integration tests: document-content search projection (M27).

End-to-end over the real app + TestClient with a SQLite database:

- committing an intake item whose extraction descriptor carries a
  ``text_key`` writes the content projection row;
- ``GET /search?text=`` matches terms INSIDE the extracted text (the
  document is found by content, not just title/metadata);
- the permission pre-filter applies to content hits exactly like
  title/metadata hits (a denied user never sees the document);
- deleting the document removes the content row after the outbox drain;
- ``POST /search/content/rebuild`` reconstructs the projection from
  durable state, idempotently.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes.documents import get_storage
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.dtos.intake import (
    KEY_INTAKE_STATUS,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.main import app

API = "/api/v1"
TEXT = (
    "This report describes the quantum entanglement experiments conducted "
    "in the superconducting laboratory during 2025."
)


def _entry(k, v):
    return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: None
    app.dependency_overrides[get_vector_repository] = lambda: None

    storage = __import__(
        "app.infrastructure.storage.local.local_storage", fromlist=["LocalFileStorage"]
    ).LocalFileStorage(str(tmp_path))
    app.dependency_overrides[get_storage] = lambda: storage

    current = {}

    def _fake_user():
        from app.core.exceptions import UnauthorizedError

        if current.get("user") is None:
            raise UnauthorizedError("Missing bearer token")
        return current["user"]

    app.dependency_overrides[get_current_user] = _fake_user

    user_a = UniversalObject.create(
        ObjectType.USER, "content.a", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:content-a-0001"),
    )
    user_b = UniversalObject.create(
        ObjectType.USER, "content.b", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:content-b-0002"),
    )

    with TestClient(app) as client:
        yield _Harness(
            client=client, session=session, storage=storage,
            user_a=user_a, user_b=user_b, set_user=lambda u: current.update(user=u),
        )

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class _Harness:
    def __init__(self, *, client, session, storage, user_a, user_b, set_user):
        self.client = client
        self.session = session
        self.storage = storage
        self.user_a = user_a
        self.user_b = user_b
        self.set_user = set_user

    def commit_document(self, *, title: str = "Lab Report 2025") -> str:
        """Seed a completed session + awaiting item with extracted text and
        commit it through the real intake commit endpoint."""
        self.set_user(self.user_a)
        repo = SQLAlchemyObjectRepository(self.session)
        session_obj = UniversalObject.create(
            ObjectType.INTAKE_SESSION, "seed", created_by="intake",
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(
                entries=(_entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value),)
            ),
        )
        session_obj.pop_domain_events()
        repo.save(session_obj)
        item = UniversalObject.create(
            ObjectType.INTAKE_ITEM, "report.pdf", created_by="intake",
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(
                entries=(
                    _entry(KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value),
                    _entry("intake.session_id", str(session_obj.id)),
                    _entry("intake.extension", "pdf"),
                    _entry("intake.mime_type", "application/pdf"),
                    _entry("intake.size_bytes", "4096"),
                    _entry("intake.sha256", "feedface"),
                    _entry("intake.staged_key", "seed/staged.pdf"),
                    _entry(
                        "intake.extraction",
                        json_encode(
                            {
                                "status": "extracted",
                                "format": "pdf",
                                "char_count": len(TEXT),
                                "text_key": "seed/extracted.txt",
                            }
                        ),
                    ),
                    _entry(
                        "intake.proposal",
                        json_encode(
                            {"title": title, "document_type": "pdf",
                             "description": "d", "confidence": 1.0}
                        ),
                    ),
                )
            ),
        )
        item.pop_domain_events()
        repo.save(item)
        self.storage.save("seed/staged.pdf", b"%PDF-1.7")
        self.storage.save("seed/extracted.txt", TEXT.encode("utf-8"))
        commit = self.client.post(f"{API}/intake/items/{item.id}/commit")
        assert commit.status_code == 200, commit.text
        return commit.json()["document_id"]

    def content_rows(self):
        return self.session.execute(
            select(DocumentContentModel).order_by(DocumentContentModel.object_id)
        ).scalars().all()


def _search(client, **params) -> list[dict]:
    res = client.get(f"{API}/search", params=params)
    assert res.status_code == 200, res.text
    return res.json()["results"]


def test_commit_writes_content_row_and_content_term_is_searchable(harness):
    doc_id = harness.commit_document()
    rows = harness.content_rows()
    assert len(rows) == 1
    assert rows[0].object_id == doc_id
    assert rows[0].source_item_id.startswith("obj:intake_item:")
    assert "quantum entanglement" in rows[0].content_text

    # The document is found by a term that appears ONLY inside the content.
    hits = _search(harness.client, text="superconducting laboratory")
    assert any(h["object_id"] == doc_id for h in hits)
    hits = _search(harness.client, text="entanglement")
    assert any(h["object_id"] == doc_id for h in hits)


def test_content_hits_respect_acl_permission_gate(harness):
    doc_id = harness.commit_document()
    # Restrict the document to user A only.
    acl = harness.client.put(
        f"{API}/objects/{doc_id}/acl",
        json={
            "readers": [str(harness.user_a.id)],
            "writers": [str(harness.user_a.id)],
            "managers": [str(harness.user_a.id)],
        },
    )
    assert acl.status_code == 200, acl.text

    harness.set_user(harness.user_a)
    hits = _search(harness.client, text="entanglement")
    assert any(h["object_id"] == doc_id for h in hits)

    # User B is denied by the ACL — the content hit must not leak.
    harness.set_user(harness.user_b)
    hits = _search(harness.client, text="entanglement")
    assert all(h["object_id"] != doc_id for h in hits)


def test_delete_removes_content_row_after_drain(harness):
    doc_id = harness.commit_document()
    assert len(harness.content_rows()) == 1
    assert harness.client.delete(f"{API}/objects/{doc_id}").status_code == 204
    # Before the drain the row is still there (eventual consistency).
    assert len(harness.content_rows()) == 1
    res = harness.client.post(f"{API}/search/index/sync")
    assert res.status_code == 200
    assert harness.content_rows() == []


def test_content_rebuild_is_deterministic_and_idempotent(harness):
    doc_id = harness.commit_document()
    harness.session.execute(  # simulate drift: drop the row
        DocumentContentModel.__table__.delete()
    )
    harness.session.commit()
    assert harness.content_rows() == []

    res = harness.client.post(f"{API}/search/content/rebuild")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["indexed"] == 1
    rows = harness.content_rows()
    assert len(rows) == 1 and rows[0].object_id == doc_id
    assert "quantum entanglement" in rows[0].content_text

    # Idempotent: a second rebuild yields the same projection.
    again = harness.client.post(f"{API}/search/content/rebuild")
    assert again.json()["indexed"] == 1
    assert len(harness.content_rows()) == 1
