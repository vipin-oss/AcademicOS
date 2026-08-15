"""V3 M11 one-document-pipeline integration tests (ADR-058)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.ports.document_revision_store import DocumentRevision
from app.infrastructure.db.models.document_revision_model import (  # noqa: F401
    DocumentRevisionModel,
)
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.document_revision_store import (
    SQLDocumentRevisionStore,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _rev(document_id="obj:document:1", version=1):
    return DocumentRevision(
        id=f"rev-{document_id}-{version}",
        document_id=document_id,
        revision_version=version,
        file_name="a.pdf",
        content_hash="abc123",
        mime_type="application/pdf",
        file_size=10,
        storage_key="documents/1/a.pdf",
        created_at="2026-08-15T00:00:00+00:00",
    )


def test_revision_versions_are_monotonic(db):
    store = SQLDocumentRevisionStore(db)
    assert store.next_version("obj:document:1") == 1
    store.add(_rev(version=1))
    db.commit()
    assert store.next_version("obj:document:1") == 2
    store.add(_rev(version=2))
    db.commit()
    revisions = store.for_document("obj:document:1")
    assert [r.revision_version for r in revisions] == [1, 2]


def test_revision_add_is_idempotent(db):
    store = SQLDocumentRevisionStore(db)
    store.add(_rev(version=1))
    db.commit()
    store.add(_rev(version=1))
    db.commit()
    assert len(store.for_document("obj:document:1")) == 1


def test_quarantine_flag_persists(db):
    store = SQLDocumentRevisionStore(db)
    rev = _rev(version=1)
    quarantined = DocumentRevision(
        **{**rev.__dict__, "quarantined": True, "quarantine_reason": "executable content"}
    )
    store.add(quarantined)
    db.commit()
    revisions = store.for_document("obj:document:1")
    assert revisions[0].quarantined is True
    assert revisions[0].quarantine_reason == "executable content"
