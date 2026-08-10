"""Integration tests: the complete S6 M1 assistant workflow over HTTP.

New conversation -> ask -> hybrid search + graph retrieval -> context ->
provider answer -> persisted -> title generated -> reload -> follow-up ->
restricted objects never appear. The semantic leg is overridden with the
reference vector repository through the search route's overrideable seam.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes.assistant import get_assistant_provider
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.assistant.providers import RuleBasedAssistantProvider
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.vector_db.fake import FakeVectorRepository
from app.main import app

API = "/api/v1/assistant"
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

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId(FAKE_USER),
    )
    session.add(ObjectModel(
            id=str(fake_user.id),
            object_type="user",
            title="test.user",
            status="active",
            version=1,
            metadata_json=[],
            audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
        )
    )
    session.commit()
    vectors = FakeVectorRepository()
    embedder = HashingEmbedder()
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_vector_repository] = lambda: vectors
    app.dependency_overrides[get_embedder] = lambda: embedder
    # Pin the deterministic rules provider (same construction as the route's
    # fallback): this suite asserts the retrieval + graph + persistence
    # workflow, so it must never depend on the developer's local AI provider
    # configuration (a configured provider selects LlmAssistantProvider and
    # reports intent="llm").
    app.dependency_overrides[get_assistant_provider] = lambda: RuleBasedAssistantProvider(
        SQLAlchemyObjectRepository(session),
        permission_evaluator=ObjectPermissionEvaluator(),
    )
    with TestClient(app) as client:
        yield client, session, vectors, embedder
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _ask(client, question: str, conversation_id: str | None = None) -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    res = client.post(f"{API}/ask", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_full_workflow_new_and_follow_up(harness):
    client, session, vectors, embedder = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.application.services.outbox import to_outbox_row
    from app.infrastructure.persistence.mapper import SnapshotMapper
    from app.infrastructure.persistence.search_mapping import (
        search_text,
        to_search_document,
    )
    from app.infrastructure.search.index_applier import SearchIndexApplier
    from app.domain.value_objects.vector import VectorDocument

    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    neighbor = UniversalObject.create(ObjectType.DOCUMENT, "Neighbor Notes", created_by="f:1")
    from app.domain.value_objects.enums import RelationshipKind

    doc.add_relationship(neighbor.id, RelationshipKind.BELONGS_TO, actor="f:1")
    for obj in (doc, neighbor):
        events = obj.pop_domain_events()
        repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])
    SearchIndexApplier(session).apply_pending()
    for obj in (doc, neighbor):
        snap = SnapshotMapper.to_snapshot(obj)
        d = to_search_document(snap)
        vectors.upsert(
            VectorDocument(
                object_id=d.object_id, object_type=d.object_type, title=d.title,
                metadata_text=d.metadata_text, version=d.version,
                vector=tuple(embedder.embed(search_text(snap))),
            )
        )

    # 1. new conversation
    first = _ask(client, "find quantum")
    conv = first["conversation"]
    assert conv["message_count"] == 2
    assert conv["title"] == "find quantum"  # auto title from the first question
    answer = first["answer"]
    assert answer["intent"] == "knowledge_search"
    card_titles = [card["title"] for card in answer["cards"]]
    assert "Quantum Paper" in card_titles
    assert "Neighbor Notes" in card_titles  # the graph leg contributed

    # 2. conversation reload (GET) — messages persisted
    got = client.get(f"{API}/conversations/{conv['id']}").json()
    assert got["conversation"]["message_count"] == 2
    assert [m["role"] for m in got["messages"]] == ["user", "assistant"]

    # 3. follow-up question on the SAME conversation
    second = _ask(client, "tell me more", conversation_id=conv["id"])
    assert second["conversation"]["id"] == conv["id"]
    assert second["conversation"]["message_count"] == 4
    # The auto title is NOT re-derived on the follow-up.
    assert second["conversation"]["title"] == "find quantum"


def test_restricted_objects_never_appear_over_http(harness):
    client, session, vectors, embedder = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.application.services.outbox import to_outbox_row
    from app.infrastructure.persistence.mapper import SnapshotMapper
    from app.infrastructure.persistence.search_mapping import (
        search_text,
        to_search_document,
    )
    from app.infrastructure.search.index_applier import SearchIndexApplier
    from app.domain.value_objects.vector import VectorDocument

    public = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Public", created_by="f:1")
    secret = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Secret", created_by="f:2")
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:someone-else"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    for obj in (public, secret):
        events = obj.pop_domain_events()
        repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])
    SearchIndexApplier(session).apply_pending()
    for obj in (public, secret):
        snap = SnapshotMapper.to_snapshot(obj)
        d = to_search_document(snap)
        vectors.upsert(
            VectorDocument(
                object_id=d.object_id, object_type=d.object_type, title=d.title,
                metadata_text=d.metadata_text, version=d.version,
                vector=tuple(embedder.embed(search_text(snap))),
            )
        )

    out = _ask(client, "find quantum")
    card_titles = [card["title"] for card in out["answer"]["cards"]]
    assert "Quantum Public" in card_titles
    assert all("Secret" not in title for title in card_titles)  # never leaks
