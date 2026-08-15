"""Integration tests: direct-upload document content indexing (Fix A).

End-to-end over the real app + TestClient with a SQLite database:

- uploading a PDF through the real ``POST /documents`` multipart endpoint
  writes the ``document_contents`` projection with the parsed BODY text
  (self-provenance: ``source_item_id`` = the document id);
- a term that exists ONLY inside the PDF body is found by ``GET /search``
  through the existing SQL content-search leg;
- the permission pre-filter applies to direct-upload content hits exactly
  like title/metadata hits (a denied user never sees the document);
- intake-committed documents behave exactly as before (unchanged).
"""
from __future__ import annotations

import io

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

from app.tests.unit.extraction_fixtures import make_pdf_bytes

API = "/api/v1"
TEXT = (
    "This report describes the quantum entanglement experiments conducted "
    "in the superconducting laboratory during 2025. The results were "
    "presented at the annual symposium on 17 March 2026."
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

    def upload_pdf(self, *, title: str = "Opaque Name", file_name: str = "opaque-name.pdf") -> str:
        """Upload a real PDF through the production ``POST /documents`` route."""
        self.set_user(self.user_a)
        res = self.client.post(
            f"{API}/documents",
            data={
                "title": title,
                "document_type": "pdf",
                "uploaded_by": str(self.user_a.id),
                "tags": "[]",
                "status": "active",
            },
            files={
                "file": (
                    file_name,
                    io.BytesIO(make_pdf_bytes(text=TEXT, title=file_name)),
                    "application/pdf",
                )
            },
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    def content_rows(self):
        return self.session.execute(
            select(DocumentContentModel).order_by(DocumentContentModel.object_id)
        ).scalars().all()


def _search(client, **params) -> list[dict]:
    res = client.get(f"{API}/search", params=params)
    assert res.status_code == 200, res.text
    return res.json()["results"]


def test_direct_upload_writes_content_row_and_body_term_is_searchable(harness):
    doc_id = harness.upload_pdf(title="Opaque Name")

    rows = harness.content_rows()
    assert len(rows) == 1, "no content row after direct PDF upload"
    assert rows[0].object_id == doc_id
    # Self-provenance: no intake item exists for a direct upload.
    assert rows[0].source_item_id == doc_id
    assert "quantum entanglement" in rows[0].content_text

    # The term exists ONLY inside the PDF body — never in title/metadata.
    hits = _search(harness.client, text="superconducting laboratory")
    assert any(h["object_id"] == doc_id for h in hits)


def test_direct_upload_content_hits_respect_acl_permission_gate(harness):
    doc_id = harness.upload_pdf(title="Opaque Name")
    assert len(harness.content_rows()) == 1

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
    hits = _search(harness.client, text="superconducting")
    assert any(h["object_id"] == doc_id for h in hits)

    # User B is denied by the ACL — the content hit must not leak.
    harness.set_user(harness.user_b)
    hits = _search(harness.client, text="superconducting")
    assert all(h["object_id"] != doc_id for h in hits)


def test_intake_commit_behavior_unchanged(harness):
    """The intake path still writes its own content row with intake
    provenance — the direct-upload change must not alter it."""
    harness.set_user(harness.user_a)
    repo = SQLAlchemyObjectRepository(harness.session)
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
                            "text_key": "seed/extracted.txt",
                        }
                    ),
                ),
                _entry(
                    "intake.proposal",
                    json_encode(
                        {"title": "Lab Report 2025", "document_type": "pdf"}
                    ),
                ),
            )
        ),
    )
    item.pop_domain_events()
    repo.save(item)
    harness.storage.save("seed/staged.pdf", b"%PDF-1.7")
    harness.storage.save("seed/extracted.txt", TEXT.encode("utf-8"))
    commit = harness.client.post(f"{API}/intake/items/{item.id}/commit")
    assert commit.status_code == 200, commit.text
    doc_id = commit.json()["document_id"]

    rows = harness.content_rows()
    assert len(rows) == 1
    assert rows[0].object_id == doc_id
    assert rows[0].source_item_id == str(item.id)  # intake provenance kept
