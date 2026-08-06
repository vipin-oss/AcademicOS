"""Integration tests for the Search API (Sprint-5 M1).

End-to-end over the real app + TestClient: the outbox-fed index lifecycle
(commit -> searchable, delete -> unsearchable), the roadmap-approved search
surface, and the permission pre-filter (unauthorized items never leak).
"""
from __future__ import annotations

import json

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
from app.application.dtos.intake import (
    KEY_INTAKE_STATUS,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.application.services.outbox import to_outbox_row
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.main import app

API = "/api/v1"
FAKE_USER = "obj:user:test-user-0001"


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
    storage = LocalFileStorage(str(tmp_path / "storage"))

    def _override_db():
        yield session

    def _override_storage():
        return storage

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId(FAKE_USER),
    )
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as client:
        yield client, session, storage
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _entry(k, v):
    return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _save_with_events(repo: SQLAlchemyObjectRepository, obj: UniversalObject) -> None:
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(event) for event in events])


def _create_object(client, *, title: str, object_type: str = "document") -> str:
    res = client.post(
        f"{API}/objects",
        json={
            "object_type": object_type,
            "title": title,
            "created_by": "x",
            "status": "active",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sync(client) -> dict:
    res = client.post(f"{API}/search/index/sync")
    assert res.status_code == 200, res.text
    return res.json()


def _search(client, **params) -> list[dict]:
    res = client.get(f"{API}/search", params=params)
    assert res.status_code == 200, res.text
    return res.json()["results"]


def _index_rows(session) -> list[SearchDocumentModel]:
    return session.execute(
        select(SearchDocumentModel).order_by(SearchDocumentModel.object_id)
    ).scalars().all()


# -------------------------------------------------------------------- auth


def test_search_and_sync_require_authentication(harness):
    client, _, _ = harness
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get(f"{API}/search", params={"text": "x"}).status_code == 401
    assert client.post(f"{API}/search/index/sync").status_code == 401


def test_search_requires_at_least_one_criterion(harness):
    client, _, _ = harness
    assert client.get(f"{API}/search").status_code == 422


# ------------------------------------------------------------- consistency


def test_commit_to_searchable_and_delete_to_unsearchable(harness):
    """Roadmap index-consistency: commit -> searchable, delete ->
    unsearchable, driven by the relay (eventual consistency by design)."""
    client, session, storage = harness
    repo = SQLAlchemyObjectRepository(session)

    # A COMPLETED session + one awaiting item with a reviewed proposal.
    session_obj = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "seed", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(_entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value),)
        ),
    )
    # Seeded with the events dropped (the pre-S5 shape), so only the
    # committed document's events flow through the outbox here.
    session_obj.pop_domain_events()
    repo.save(session_obj)
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM, "seed.pdf", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry(KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value),
                _entry("intake.session_id", str(session_obj.id)),
                _entry("intake.extension", "pdf"),
                _entry("intake.mime_type", "application/pdf"),
                _entry("intake.size_bytes", "1024"),
                _entry("intake.sha256", "feedface"),
                _entry("intake.staged_key", "seed/staged.pdf"),
                _entry(
                    "intake.extraction",
                    json_encode({"status": "extracted", "format": "pdf", "char_count": 5}),
                ),
                _entry(
                    "intake.proposal",
                    json_encode({"title": "seed.pdf", "document_type": "pdf",
                                 "description": "d", "confidence": 1.0}),
                ),
            )
        ),
    )
    item.pop_domain_events()
    repo.save(item)
    storage.save("seed/staged.pdf", b"%PDF-1.7")

    commit = client.post(f"{API}/intake/items/{item.id}/commit")
    assert commit.status_code == 200, commit.text
    doc_id = commit.json()["document_id"]

    # Eventual consistency: not searchable until the outbox is drained.
    assert _search(client, text="seed") == []
    # 4 events: the document's ObjectCreated + RelationshipAdded, plus the
    # item's two MetadataChanged marks (its commit transition is durable
    # too — every write path feeds the relay).
    assert _sync(client) == {"applied": 4}
    # The item (title "seed.pdf") is now searchable alongside the document.
    hits = _search(client, title="seed.pdf")
    assert sorted(h["object_id"] for h in hits) == sorted([str(item.id), doc_id])
    assert _search(client, object_type="document")[0]["object_id"] == doc_id
    assert _search(client, text="seed")[0]["version"] >= 1

    # Delete -> the deleted object is unsearchable after the next drain
    # (ObjectDeleted event), while the item remains searchable.
    assert client.delete(f"{API}/objects/{doc_id}").status_code == 204
    assert _search(client, text="seed") != []  # still visible until drained
    _sync(client)
    after = _search(client, text="seed")
    assert [h["object_id"] for h in after] == [str(item.id)]
    assert _search(client, object_type="document") == []


def test_update_reflects_new_version_after_sync(harness):
    client, session, _ = harness
    doc_id = _create_object(client, title="Original Title")
    _sync(client)

    res = client.put(
        f"{API}/objects/{doc_id}",
        json={"status": "archived", "updated_by": "x"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2

    # Index still reflects v1 until the relay runs (eventual consistency).
    assert _search(client, title="Original Title")[0]["version"] == 1
    _sync(client)
    hits = _search(client, title="Original Title")
    assert len(hits) == 1
    assert hits[0]["version"] == 2
    assert hits[0]["object_id"] == doc_id


def test_replay_sync_is_idempotent(harness):
    client, session, _ = harness
    _create_object(client, title="Stable Doc")
    _sync(client)
    first = _search(client, text="stable")
    assert len(first) == 1
    # Re-syncing an empty outbox changes nothing and duplicates nothing.
    assert _sync(client) == {"applied": 0}
    assert _search(client, text="stable") == first
    assert len(_index_rows(session)) == 1


# ------------------------------------------------------------ permissions


def test_search_never_leaks_restricted_objects(harness):
    """An object whose ACL excludes the caller stays in the INDEX but is
    never RETURNED — the API gate is the R4 evaluator, not the index."""
    client, session, _ = harness
    repo = SQLAlchemyObjectRepository(session)

    _create_object(client, title="Public Paper")  # no ACL -> open
    restricted = UniversalObject.create(
        ObjectType.DOCUMENT, "Confidential Paper", created_by="f:other"
    )
    restricted.set_metadata(
        _entry("acl.readers", json.dumps(["obj:user:allowed-0009"])),
        actor="system",
    )
    _save_with_events(repo, restricted)  # indexed by the drain
    _sync(client)

    assert len(_index_rows(session)) == 2  # both rows are in the index...
    hits = _search(client, text="paper")
    assert [h["title"] for h in hits] == ["Public Paper"]  # ...but the API
    # only returns what the caller may READ


def test_search_metadata_text(harness):
    client, _, _ = harness
    res = client.post(
        f"{API}/objects",
        json={
            "object_type": "grant",
            "title": "Quantum Grant",
            "created_by": "x",
            "status": "active",
            "metadata": [
                {"key": "dc.subject", "value": "entanglement", "layer": 1, "source": "system"},
            ],
        },
    )
    assert res.status_code == 201, res.text
    _sync(client)
    hits = _search(client, text="entanglement")
    assert [h["object_id"] for h in hits] == [res.json()["id"]]
