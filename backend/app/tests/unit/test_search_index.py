"""Unit tests for the Global Search Foundation (Sprint-5 M1).

Real SQLite + the real adapters (object repository, outbox relay, search
repository, applier): the search projection must be derived, deterministic,
version-aware, replayable from durable events, and rebuildable from version
snapshots — never the source of truth.
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.application.exceptions import ValidationError
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.search import SearchDocument
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.outbox_model import OutboxEventModel
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.outbox.relay import OutboxRelay
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import to_search_document
from app.infrastructure.persistence.snapshots import (
    MetadataSnapshot,
    ObjectSnapshot,
    object_snapshot_from_dict,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier


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


@pytest.fixture()
def repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _save_with_events(repo: SQLAlchemyObjectRepository, obj: UniversalObject) -> None:
    """The sanctioned write path: aggregate events become outbox rows in the
    same transaction as the save (mirrors CreateDocumentUseCase)."""
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(event) for event in events])


def _index_rows(db) -> list[SearchDocumentModel]:
    return db.execute(
        select(SearchDocumentModel).order_by(SearchDocumentModel.object_id)
    ).scalars().all()


def _pending_events(db) -> list[dict]:
    return OutboxRelay(db).pending()


# ------------------------------------------------------------- outbox -> index


def test_initial_indexing_via_drain(db, repo):
    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "Alpha Paper", created_by="f:1", status=ObjectStatus.ACTIVE
    )
    _save_with_events(repo, obj)

    out = SearchIndexApplier(db).apply_pending()
    assert out == {"applied": 1}

    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].object_id == str(obj.id)
    assert rows[0].object_type == "document"
    assert rows[0].title == "Alpha Paper"
    assert rows[0].version == 1
    assert _pending_events(db) == []  # the event was marked delivered


def test_reindex_after_update(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Alpha", created_by="f:1")
    _save_with_events(repo, obj)
    SearchIndexApplier(db).apply_pending()

    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("Beta", actor="f:1")
    _save_with_events(repo, loaded)
    SearchIndexApplier(db).apply_pending()

    rows = _index_rows(db)
    assert len(rows) == 1  # still one row — the projection, not a history
    assert rows[0].title == "Beta"
    assert rows[0].version == 2


def test_delete_removes_search_document(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Gone", created_by="f:1")
    _save_with_events(repo, obj)
    SearchIndexApplier(db).apply_pending()
    assert len(_index_rows(db)) == 1

    repo.delete(obj.id)
    assert any(
        e["event_type"] == "ObjectDeleted" for e in _pending_events(db)
    )  # durable, replayable deletion marker
    SearchIndexApplier(db).apply_pending()

    assert _index_rows(db) == []
    assert _pending_events(db) == []


def test_replay_idempotency(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Stable", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db)
    applier.apply_pending()
    first = [(r.object_id, r.title, r.version) for r in _index_rows(db)]

    # Re-draining an empty outbox changes nothing; re-issuing the same
    # events (as new rows with fresh event ids) still upserts, never
    # duplicates.
    assert applier.apply_pending() == {"applied": 0}
    assert [(r.object_id, r.title, r.version) for r in _index_rows(db)] == first

    loaded = repo.get(obj.id)
    assert loaded is not None
    _save_with_events(repo, loaded)  # unchanged aggregate: no event, no change
    assert applier.apply_pending() == {"applied": 0}
    assert [(r.object_id, r.title, r.version) for r in _index_rows(db)] == first


def test_explicit_rows_and_pending_events_cannot_double_write(db, repo):
    """Passing explicit outbox rows for events that are STILL pending on
    the aggregate (no pop) must produce exactly one persisted row — the
    two channels are deduplicated by event_id within the same save."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Both", created_by="f:1")
    events = obj.domain_events  # deliberately NOT popped
    assert len(events) == 1
    repo.save(obj, outbox_events=[to_outbox_row(events[0])])

    pending = _pending_events(db)
    assert [e["event_type"] for e in pending] == ["ObjectCreated"]
    assert len(pending) == 1  # the explicit row; the auto-emit skipped it


def test_resave_with_pending_events_never_duplicates(db, repo):
    """Saving the same aggregate twice while its events are un-popped must
    not duplicate outbox rows — event_id is the durable idempotency key
    (this is how the assistant flow saves a conversation twice)."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Twice", created_by="f:1")
    repo.save(obj)  # auto-emits ObjectCreated, events stay on the aggregate
    repo.save(obj)  # same pending event -> skipped

    pending = _pending_events(db)
    assert [e["event_type"] for e in pending] == ["ObjectCreated"]
    SearchIndexApplier(db).apply_pending()
    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "Twice"


def test_duplicate_event_handling(db, repo):
    """Re-issuing the same event content (fresh event id, e.g. after a
    crash between apply and mark) converges to the same single row."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Dup", created_by="f:1")
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(events[0])])
    SearchIndexApplier(db).apply_pending()

    # A duplicate delivery of the same logical event.
    event = events[0]
    obj2 = repo.get(obj.id)
    assert obj2 is not None
    dup = to_outbox_row(type(event)(aggregate_id=obj2.id, title="Dup"))
    db.add(OutboxEventModel(**dup))
    db.commit()
    SearchIndexApplier(db).apply_pending()

    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "Dup"
    assert rows[0].version == 1


def test_out_of_order_application_is_stable(db, repo):
    """The applier derives the CURRENT document from durable state, so
    applying events out of order still converges to the latest state."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "v1 title", created_by="f:1")
    _save_with_events(repo, obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("v2 title", actor="f:1")
    _save_with_events(repo, loaded)

    # Reverse drain order by applying the second event's batch first is not
    # possible through the relay (oldest first) — so emulate a concurrent
    # rebuild + stale drain: rebuild at v2, then apply the v1 event again.
    from app.domain.events import ObjectCreated

    applier = SearchIndexApplier(db)
    applier.rebuild()
    stale = to_outbox_row(ObjectCreated(aggregate_id=obj.id, title="v1 title"))
    db.add(OutboxEventModel(**stale))
    db.commit()
    applier.apply_pending()
    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "v2 title"  # no regression to the stale state
    assert rows[0].version == 2


def test_version_guard_rejects_stale_upsert(db):
    """The adapter's atomic version guard: a stale document can never
    overwrite a newer stored projection."""
    index = SQLAlchemySearchRepository(db)
    index.upsert(
        SearchDocument(
            object_id="obj:document:X", object_type="document",
            title="new", metadata_text="", version=5,
        )
    )
    db.commit()
    index.upsert(
        SearchDocument(
            object_id="obj:document:X", object_type="document",
            title="stale", metadata_text="", version=3,
        )
    )
    db.commit()
    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "new"
    assert rows[0].version == 5


# ------------------------------------------------------------------- rebuild


def test_rebuild_from_version_snapshots_matches_drain(db, repo):
    obj = UniversalObject.create(ObjectType.COURSE, "Physics 101", created_by="f:1")
    _save_with_events(repo, obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("Physics 201", actor="f:1")
    loaded.set_metadata(
        MetadataEntry("dc.subject", "mechanics", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="system",
    )
    _save_with_events(repo, loaded)
    obj2 = UniversalObject.create(ObjectType.DOCUMENT, "Notes", created_by="f:1")
    _save_with_events(repo, obj2)

    applier = SearchIndexApplier(db)
    applier.apply_pending()
    drained = {(r.object_id, r.object_type, r.title, r.metadata_text, r.version) for r in _index_rows(db)}

    # Scramble the index, then rebuild purely from version snapshots.
    db.execute(__import__("sqlalchemy").delete(SearchDocumentModel))
    db.commit()
    applier.rebuild()
    rebuilt = {(r.object_id, r.object_type, r.title, r.metadata_text, r.version) for r in _index_rows(db)}

    assert rebuilt == drained
    assert {r.title for r in _index_rows(db)} == {"Physics 201", "Notes"}


def test_rebuild_is_atomic_on_failure(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Atomic", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db)
    applier.apply_pending()
    before = [(r.object_id, r.title, r.version) for r in _index_rows(db)]

    real_commit = db.commit

    def failing_commit() -> None:
        raise OperationalError(
            "DELETE search_documents", (), sqlite3.OperationalError("disk I/O error")
        )

    db.commit = failing_commit
    with pytest.raises(OperationalError):
        applier.rebuild()
    db.commit = real_commit
    # The cleared table was rolled back: the pre-rebuild state survives.
    assert [(r.object_id, r.title, r.version) for r in _index_rows(db)] == before


def test_rebuild_clears_stale_documents(db, repo):
    """A deleted object's projection (delete event not yet drained) is
    dropped by a rebuild — the index is rebuilt from durable state only."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Live", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db)
    applier.apply_pending()
    assert len(_index_rows(db)) == 1
    repo.delete(obj.id)
    # Delete event still pending; the stale projection is present...
    assert len(_index_rows(db)) == 1
    # ...but a rebuild derives from version history and clears it.
    applier.rebuild()
    assert _index_rows(db) == []
    # And the pending delete event still drains cleanly afterwards.
    applier.apply_pending()
    assert _index_rows(db) == []


# ------------------------------------------------------------ deterministic map


def test_deterministic_mapping():
    base = ObjectSnapshot(
        id="obj:document:A",
        object_type="document",
        title="Title",
        status="active",
        version=3,
        metadata=(
            MetadataSnapshot("z.key", "v1", 1, "system", recorded_at="2026-01-01T00:00:00+00:00"),
            MetadataSnapshot("a.key", "v2", 1, "system", recorded_at="2026-01-01T00:00:00+00:00"),
        ),
    )
    # Metadata order does not matter: the mapping canonicalises by key.
    swapped = ObjectSnapshot(
        id="obj:document:A",
        object_type="document",
        title="Title",
        status="active",
        version=3,
        metadata=(
            MetadataSnapshot("a.key", "v2", 1, "system", recorded_at="2026-01-01T00:00:00+00:00"),
            MetadataSnapshot("z.key", "v1", 1, "system", recorded_at="2026-01-01T00:00:00+00:00"),
        ),
    )
    first = to_search_document(base)
    assert first == to_search_document(swapped)
    assert first.metadata_text == "a.key: v2\nz.key: v1"
    assert first.object_id == "obj:document:A"
    assert first.version == 3


def test_snapshot_dict_round_trip(db, repo):
    """object_snapshot_from_dict(to_dict()) is lossless — rebuilds lift the
    stored representation exactly."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Round", created_by="f:1")
    obj.set_metadata(
        MetadataEntry("dc.subject", "physics", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="system",
    )
    _save_with_events(repo, obj)
    snap = SnapshotMapper.to_snapshot(obj)
    assert object_snapshot_from_dict(snap.to_dict()) == snap


# ------------------------------------------------------------------ rollback


def test_drain_rollback_leaves_outbox_pending(db, repo):
    """A failing commit discards the batch's index writes AND its delivery
    marks — the events stay pending and the next drain converges."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Retry me", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db)

    calls = {"n": 0}
    real_commit = db.commit

    def flaky_commit() -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise OperationalError(
                "UPDATE outbox_events", (), sqlite3.OperationalError("database is locked")
            )
        real_commit()

    db.commit = flaky_commit
    assert applier.apply_pending() == {"applied": 1}
    # Two transient lock failures absorbed: attempts 1-2 fail inside
    # mark_delivered, attempt 3 lands, and the outer commit_with_retry
    # commit is a no-op afterwards (mark_delivered already committed).
    assert calls["n"] == 4
    rows = _index_rows(db)
    assert len(rows) == 1  # retried batch wrote exactly one row
    assert _pending_events(db) == []


def test_drain_failure_rolls_back_batch(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Doomed", created_by="f:1")
    _save_with_events(repo, obj)

    def failing_commit() -> None:
        raise OperationalError(
            "UPDATE outbox_events", (), sqlite3.OperationalError("disk I/O error")
        )

    real_commit = db.commit
    db.commit = failing_commit
    with pytest.raises(OperationalError):
        SearchIndexApplier(db).apply_pending()
    db.commit = real_commit
    db.rollback()

    assert _index_rows(db) == []  # nothing applied
    assert len(_pending_events(db)) == 1  # event still pending -> replayable

    # Converges once the store cooperates again.
    SearchIndexApplier(db).apply_pending()
    assert len(_index_rows(db)) == 1


# -------------------------------------------------------------------- search


def _seed_documents(db, repo, *objects: UniversalObject) -> None:
    for obj in objects:
        _save_with_events(repo, obj)
    SearchIndexApplier(db).apply_pending()


def test_search_exact_title(db, repo):
    a = UniversalObject.create(ObjectType.DOCUMENT, "Exact Title Here", created_by="f:1")
    b = UniversalObject.create(ObjectType.DOCUMENT, "Another Title", created_by="f:1")
    _seed_documents(db, repo, a, b)
    index = SQLAlchemySearchRepository(db)

    hits = index.search(title="exact title here")  # case-insensitive exact
    assert [h.object_id for h in hits] == [str(a.id)]
    hits = index.search(title="Exact")  # not a substring match
    assert hits == []


def test_search_object_type(db, repo):
    a = UniversalObject.create(ObjectType.DOCUMENT, "Doc", created_by="f:1")
    b = UniversalObject.create(ObjectType.COURSE, "Course", created_by="f:1")
    _seed_documents(db, repo, a, b)
    index = SQLAlchemySearchRepository(db)
    assert [h.object_id for h in index.search(object_type="course")] == [str(b.id)]
    assert len(index.search(object_type="document")) == 1


def test_search_text_matches_title_and_metadata(db, repo):
    a = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Mechanics Notes", created_by="f:1")
    a.set_metadata(
        MetadataEntry("dc.subject", "entanglement", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="system",
    )
    b = UniversalObject.create(ObjectType.COURSE, "History 101", created_by="f:1")
    _seed_documents(db, repo, a, b)
    index = SQLAlchemySearchRepository(db)

    assert [h.object_id for h in index.search(text="quantum")] == [str(a.id)]  # title
    assert [h.object_id for h in index.search(text="entanglement")] == [str(a.id)]  # metadata
    assert [h.object_id for h in index.search(text="QUANTUM")] == [str(a.id)]  # case-insensitive
    assert index.search(text="zzz") == []


def test_search_combined_filters_and_deterministic_order(db, repo):
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Doc {i}", created_by="f:1")
        for i in range(3)
    ]
    _seed_documents(db, repo, *docs)
    index = SQLAlchemySearchRepository(db)

    hits = index.search(text="doc", object_type="document", limit=50)
    assert [h.object_id for h in hits] == sorted(h.object_id for h in hits)  # deterministic
    assert len(index.search(text="doc", object_type="course")) == 0
    assert len(index.search(text="doc", limit=2)) == 2  # bounded


def test_search_escapes_like_wildcards(db, repo):
    a = UniversalObject.create(ObjectType.DOCUMENT, "100% funded", created_by="f:1")
    b = UniversalObject.create(ObjectType.DOCUMENT, "1000 funded", created_by="f:1")
    _seed_documents(db, repo, a, b)
    index = SQLAlchemySearchRepository(db)

    hits = index.search(text="100%")  # '%' must be literal
    assert [h.object_id for h in hits] == [str(a.id)]


# ---------------------------------------------------------------- use case ACL


def _user(obj_id: str = "obj:user:alice-0001") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId(obj_id),
    )


def test_use_case_requires_a_criterion(db, repo):
    use_case = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator()
    )
    with pytest.raises(ValidationError):
        use_case.execute(user=_user())


def test_use_case_prefilters_by_read_permission(db, repo):
    open_doc = UniversalObject.create(ObjectType.DOCUMENT, "Open Doc", created_by="f:1")
    restricted = UniversalObject.create(
        ObjectType.DOCUMENT, "Secret Doc", created_by="f:2"
    )
    restricted.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    _seed_documents(db, repo, open_doc, restricted)

    use_case = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator()
    )
    alice = _user("obj:user:alice-0001")
    bob = _user("obj:user:bob-0002")

    for candidate in use_case.execute(user=alice, text="doc"):
        assert candidate.object_id == str(open_doc.id)  # unauthorized never leaks
    hits = use_case.execute(user=bob, text="doc")
    assert {h.object_id for h in hits} == {str(open_doc.id), str(restricted.id)}


def test_use_case_never_leaks_deleted_rows(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Ghost", created_by="f:1")
    _save_with_events(repo, obj)
    SearchIndexApplier(db).apply_pending()
    repo.delete(obj.id)
    # Delete event NOT yet drained: the index row still exists...
    use_case = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator()
    )
    # ...but the authoritative object is gone, so the candidate is dropped.
    assert use_case.execute(user=_user(), text="ghost") == []
    SearchIndexApplier(db).apply_pending()
    assert SQLAlchemySearchRepository(db).search(text="ghost") == []


def test_same_session_read_after_upsert_is_fresh(db):
    """Core upserts do not synchronize the identity map; the adapter expires
    cached rows so a same-session read-after-write stays honest."""
    index = SQLAlchemySearchRepository(db)
    index.upsert(SearchDocument(
        object_id="obj:document:S", object_type="document", title="Old",
        metadata_text="", version=1,
    ))
    db.commit()
    assert _index_rows(db)  # populate the identity map
    index.upsert(SearchDocument(
        object_id="obj:document:S", object_type="document", title="New",
        metadata_text="", version=2,
    ))
    db.commit()
    rows = _index_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "New" and rows[0].version == 2
