"""Unit tests for immutable version snapshots (Sprint-4 Milestone B).

Real SQLite + the real repository adapter: every version an object ever
stores must get exactly one immutable ``object_versions`` row, written in the
SAME transaction as the aggregate save — durable across restarts, absent
after rollback or a CAS conflict, and never duplicated by a retry.
"""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.domain.entities.object import UniversalObject
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.models.object_version_model import ObjectVersionModel
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


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


def _version_rows(session) -> list[ObjectVersionModel]:
    return session.execute(
        select(ObjectVersionModel).order_by(
            ObjectVersionModel.object_id, ObjectVersionModel.version
        )
    ).scalars().all()


def test_create_records_first_version_snapshot(db):
    """First version: a create stores exactly one row for version 1, holding
    the existing ObjectSnapshot representation (no new format)."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Paper", created_by="f:1")
    SQLAlchemyObjectRepository(db).save(obj)

    rows = _version_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.object_id == str(obj.id)
    assert row.version == 1
    assert row.created_at  # ISO-8601 timestamp present
    assert row.snapshot == SnapshotMapper.to_snapshot(obj).to_dict()
    assert row.snapshot["id"] == str(obj.id)
    assert row.snapshot["title"] == "Paper"
    assert row.snapshot["version"] == 1


def test_updates_record_subsequent_version_snapshots(db):
    """Subsequent versions: each version bump adds a row; earlier rows keep
    the state that version had (immutable snapshot contents)."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "v1", created_by="f:1")
    repo.save(obj)

    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("v2", actor="f:1")
    repo.save(loaded)

    again = repo.get(obj.id)
    assert again is not None
    again.change_status(ObjectStatus.ARCHIVED, actor="f:1")
    repo.save(again)

    rows = _version_rows(db)
    assert [(r.version, r.snapshot["title"], r.snapshot["status"]) for r in rows] == [
        (1, "v1", "draft"),
        (2, "v2", "draft"),
        (3, "v2", "archived"),
    ]
    # The v1 row is byte-identical to the original snapshot even after later
    # versions were written — the recorded content is immutable.
    assert rows[0].snapshot == SnapshotMapper.to_snapshot(obj).to_dict()
    assert rows[0].snapshot == {
        "id": str(obj.id),
        "object_type": "document",
        "title": "v1",
        "status": "draft",
        "version": 1,
        "metadata": [],
        "relationships": [],
        "audit": rows[0].snapshot["audit"],
    }
    assert rows[0].snapshot["audit"]["created_by"] == "f:1"


def test_unchanged_save_writes_no_version_row(db):
    """Re-saving an aggregate whose version did not change records nothing."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Same", created_by="f:1")
    repo.save(obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    repo.save(loaded)  # no mutation -> version unchanged
    assert len(_version_rows(db)) == 1


def test_duplicate_version_is_rejected(db):
    """Duplicate version protection: the (object_id, version) UNIQUE
    constraint rejects a second row for the same version."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Dup", created_by="f:1")
    SQLAlchemyObjectRepository(db).save(obj)

    with pytest.raises(IntegrityError):
        db.add(
            ObjectVersionModel(
                object_id=str(obj.id),
                version=1,
                snapshot={"id": str(obj.id), "title": "forged"},
                created_at="2026-08-06T00:00:00+00:00",
            )
        )
        db.commit()
    db.rollback()
    assert len(_version_rows(db)) == 1


def test_cas_conflict_leaves_no_version_row(db):
    """A stale save refused by optimistic concurrency writes nothing — not
    even the version row for the would-be version."""
    engine = db.get_bind()
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    repo_a = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Race", created_by="f:1")
    repo_a.save(obj)

    # The stale aggregate is loaded at version 1 and kept across the
    # concurrent writer's save.
    stale = repo_a.get(obj.id)
    assert stale is not None and stale.version == 1

    # Concurrent writer advances the object to version 2.
    session_b = maker()
    repo_b = SQLAlchemyObjectRepository(session_b)
    concurrent = repo_b.get(obj.id)
    assert concurrent is not None
    concurrent.rename("by B", actor="f:2")
    repo_b.save(concurrent)

    # The stale aggregate is renamed twice -> version 3, then refused.
    stale.rename("by A", actor="f:1")
    stale.rename("by A again", actor="f:1")
    assert stale.version == 3
    with pytest.raises(OptimisticConcurrencyError, match="changed since it was loaded"):
        repo_a.save(stale)

    session_b.close()
    rows = _version_rows(db)
    # Only the winning writer's versions exist; the loser left no orphan row.
    assert [(r.version, r.snapshot["title"]) for r in rows] == [(1, "Race"), (2, "by B")]
    stored_version = db.execute(
        select(ObjectModel.version).where(ObjectModel.id == str(obj.id))
    ).scalar()
    assert stored_version == 2


def test_retry_safety_writes_exactly_one_version_row(db):
    """A lock-contention retry re-issues the write lambda; the version row
    must land exactly once, never duplicated by the retried attempt."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Retry", created_by="f:1")

    calls = {"n": 0}
    real_commit = db.commit

    def flaky_commit() -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise OperationalError(
                "INSERT object_versions", (), sqlite3.OperationalError("database is locked")
            )
        real_commit()

    db.commit = flaky_commit
    repo.save(obj)
    assert calls["n"] == 3  # two transient failures absorbed, third lands

    rows = _version_rows(db)
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].snapshot["title"] == "Retry"


def test_rollback_discards_version_row_with_object(db):
    """A commit failure rolls back the object row AND the version row — no
    version history can survive a failed save."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Doomed", created_by="f:1")

    def failing_commit() -> None:
        raise OperationalError(
            "INSERT object_versions", (), sqlite3.OperationalError("disk I/O error")
        )

    db.commit = failing_commit
    with pytest.raises(OperationalError):
        repo.save(obj)

    assert db.query(ObjectModel).count() == 0
    assert db.query(ObjectVersionModel).count() == 0


def test_version_rows_survive_restart(db):
    """Committed version rows are durable: a fresh session over the same DB
    still sees the full history."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Crash", created_by="f:1")
    repo.save(obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("Crash2", actor="f:1")
    repo.save(loaded)
    db.close()

    engine = db.get_bind()
    fresh = sessionmaker(bind=engine, expire_on_commit=False)()
    rows = _version_rows(fresh)
    assert [(r.version, r.snapshot["title"]) for r in rows] == [(1, "Crash"), (2, "Crash2")]
    fresh.close()


def test_delete_removes_version_rows(db):
    """Deleting an object removes its version history in the same transaction
    (SQLite parity with PostgreSQL's ON DELETE CASCADE)."""
    repo = SQLAlchemyObjectRepository(db)
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Gone", created_by="f:1")
    repo.save(obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("Gone2", actor="f:1")
    repo.save(loaded)
    assert len(_version_rows(db)) == 2

    repo.delete(obj.id)
    assert db.query(ObjectModel).count() == 0
    assert _version_rows(db) == []


def test_commit_path_records_committed_document_version(db):
    """Roadmap link: a committed intake item yields a document whose first
    stored version snapshot is on record — the committed object carries its
    version. (The document is created and given its BELONGS_TO link in
    memory before its first save, so its first STORED version is 2 — version
    rows mirror stored versions, exactly as they occurred.)"""
    from app.application.dtos.intake import (
        KEY_INTAKE_STATUS,
        IntakeItemStatus,
        IntakeSessionStatus,
        json_encode,
    )
    from app.application.intake.commit_engine import CommitEngineService
    from app.application.ports.file_storage import FileStorage
    from app.domain.value_objects.metadata import Metadata, MetadataEntry, MetadataLayer, Provenance

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

    def entry(k, v):
        return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)

    repo = SQLAlchemyObjectRepository(db)
    storage = InMemoryFileStorage()
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

    out = CommitEngineService(repo, storage).commit_item(str(item.id), actor="faculty:1")
    doc_id = out.document_id

    doc_rows = [r for r in _version_rows(db) if r.object_id == doc_id]
    assert len(doc_rows) == 1
    assert doc_rows[0].version == 2
    snap = doc_rows[0].snapshot
    assert snap["id"] == doc_id
    assert snap["object_type"] == "document"
    assert snap["title"] == "p.pdf"
    assert snap["version"] == 2

    # The item's committed terminal state is on record too, pointing at the
    # document — its intermediate version 2 was never stored, so no row.
    item_rows = [r for r in _version_rows(db) if r.object_id == str(item.id)]
    assert [r.version for r in item_rows] == [1, 3]
    committed = item_rows[-1].snapshot
    meta = {m["key"]: m["value"] for m in committed["metadata"]}
    assert meta["intake.status"] == "committed"
    assert meta["intake.committed_document"] == doc_id
