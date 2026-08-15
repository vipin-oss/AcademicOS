"""Unit tests for the durable outbox (Sprint-4 Milestone A).

Real SQLite + the real repository adapter: events must ride the SAME
transaction as the aggregate write, survive a retry, survive a "crash"
(new session), and be replayable through the relay.
"""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import CreateDocumentInput
from app.application.intake.commit_engine import CommitEngineService
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.outbox_model import OutboxEventModel
from app.infrastructure.outbox.relay import OutboxRelay
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


class InMemoryFileStorage(FileStorage):
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.blobs[key] = bytes(content)

    def read(self, key: str) -> bytes:
        if key not in self.blobs:
            raise FileNotFoundError(key)
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _pending_rows(session) -> list[OutboxEventModel]:
    return session.execute(
        select(OutboxEventModel).order_by(OutboxEventModel.id)
    ).scalars().all()


def test_document_creation_appends_outbox_row_transactionally(db):
    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()

    CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title="Paper",
                document_type="pdf",
                uploaded_by="faculty:1",
                file_name="paper.pdf",
                file_size=10,
                mime_type="application/pdf",
                content=b"%PDF-1.7",
                status=ObjectStatus.ACTIVE,
            )
        )
    )

    rows = _pending_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "ObjectCreated"
    assert row.aggregate_id.startswith("obj:document:")
    assert row.payload["object_type"] == "document"
    assert row.payload["title"] == "Paper"
    assert row.delivered_at is None


def test_commit_path_appends_outbox_row(db):
    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()
    # Seed a completed session + awaiting item + proposal, then commit.
    from app.application.dtos.intake import (
        KEY_INTAKE_STATUS,
        IntakeItemStatus,
        IntakeSessionStatus,
        json_encode,
    )
    from app.domain.value_objects.metadata import Metadata, MetadataEntry, MetadataLayer, Provenance

    def entry(k, v):
        return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)

    session_obj = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "s", created_by="intake", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value),)),
    )
    repo.save(session_obj)
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM, "p.pdf", created_by="intake", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(
            entry(KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value),
            entry("intake.session_id", str(session_obj.id)),
            entry("intake.extension", "pdf"),
            entry("intake.mime_type", "application/pdf"),
            entry("intake.size_bytes", "10"),
            entry("intake.sha256", "abc"),
            entry("intake.staged_key", "k"),
            entry("intake.extraction", json_encode({"status": "extracted", "format": "pdf", "char_count": 3})),
            entry("intake.proposal", json_encode({"title": "p.pdf", "document_type": "pdf", "description": "d", "confidence": 1.0})),
        )),
    )
    repo.save(item)
    storage.save("k", b"%PDF-1.7")

    CommitEngineService(repo, storage).commit_item(str(item.id), actor="faculty:1")

    rows = _pending_rows(db)
    assert any(r.event_type == "ObjectCreated" and r.aggregate_id.startswith("obj:document:") for r in rows)


def test_outbox_row_survives_lock_contention_retry(db):
    """The outbox row is added INSIDE the write lambda, so a lock-contention
    retry re-issues it — the event is never lost by the retry path."""
    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()
    use_case = CreateDocumentUseCase(repo, storage)

    calls = {"n": 0}
    real_commit = db.commit

    def flaky_commit() -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise OperationalError(
                "UPDATE objects", (), sqlite3.OperationalError("database is locked")
            )
        real_commit()

    db.commit = flaky_commit
    use_case.execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title="Retry",
                document_type="txt",
                uploaded_by="faculty:1",
                file_name="r.txt",
                file_size=1,
                mime_type="text/plain",
                content=b"x",
                status=ObjectStatus.ACTIVE,
            )
        )
    )
    assert calls["n"] == 3  # two transient failures absorbed, third lands
    rows = _pending_rows(db)
    assert len(rows) == 1  # the retried write still carried the event


def test_outbox_row_survives_crash_before_relay(db):
    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()
    CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title="Crash", document_type="txt", uploaded_by="faculty:1",
                file_name="c.txt", file_size=1, mime_type="text/plain",
                content=b"y", status=ObjectStatus.ACTIVE,
            )
        )
    )
    db.close()

    # "Restart": a fresh session over the same DB still sees the event.
    engine = db.get_bind()
    fresh = sessionmaker(bind=engine, expire_on_commit=False)()
    rows = _pending_rows(fresh)
    assert len(rows) == 1
    assert rows[0].event_type == "ObjectCreated"
    fresh.close()


def test_relay_pending_and_mark_delivered_idempotent(db):
    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()
    CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title="Relay", document_type="txt", uploaded_by="faculty:1",
                file_name="l.txt", file_size=1, mime_type="text/plain",
                content=b"z", status=ObjectStatus.ACTIVE,
            )
        )
    )
    relay = OutboxRelay(db)
    pending = relay.pending()
    assert len(pending) == 1
    assert pending[0]["event_type"] == "ObjectCreated"
    assert pending[0]["aggregate_id"].startswith("obj:document:")
    assert "payload" in pending[0]

    event_id = pending[0]["event_id"]
    marked = relay.mark_delivered([event_id], at="2026-08-06T00:00:00+00:00")
    assert marked == 1
    assert relay.pending() == []

    # Idempotent: marking again changes nothing.
    assert relay.mark_delivered([event_id], at="2026-08-06T00:00:00+00:00") == 0


def test_event_id_is_the_unique_idempotency_key(db):
    """Re-issuing the same event row violates the unique event_id — a
    duplicate commit can never write a duplicate event."""
    from sqlalchemy.exc import IntegrityError

    from app.application.services.outbox import to_outbox_row
    from app.domain.events import ObjectCreated

    obj = UniversalObject.create(ObjectType.DOCUMENT, "Dup", created_by="f:1")
    event = ObjectCreated(aggregate_id=obj.id, object_type="document", title="Dup")
    row = to_outbox_row(event)
    db.add(OutboxEventModel(**row))
    db.commit()
    with pytest.raises(IntegrityError):  # unique event_id
        db.add(OutboxEventModel(**row))
        db.commit()
    db.rollback()
