"""Integration tests for the assistant memory recall API (Sprint-8 M1).

Full TestClient surface of ``GET /assistant/memory/recall``: the 401
gate, empty recall on an empty world, recall of indexed conversations
with the preserved citations and review gating, the graph-aware
knowledge leg, query/limit validation (422), and determinism.

Mirrors ``test_assistant_api.py`` / ``test_eval_history_api.py``:
StaticPool in-memory SQLite, the app imported via ``pytest.importorskip``,
``get_db`` / ``get_current_user`` overridden, indexing done through the
REAL ``SearchIndexApplier`` + vector store the production stack uses.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.dependencies.auth import get_current_user  # noqa: E402
from app.application.dtos.assistant import (  # noqa: E402
    AssistantAnswerOutput,
    AssistantCitation,
)
from app.application.use_cases.assistant.helpers import (  # noqa: E402
    append_message,
    create_conversation_object,
)
from app.domain.entities.object import UniversalObject  # noqa: E402
from app.domain.value_objects.enums import (  # noqa: E402
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer  # noqa: E402
from app.domain.value_objects.object_id import ObjectId  # noqa: E402
from app.domain.value_objects.vector import VectorDocument  # noqa: E402
from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder  # noqa: E402
from app.infrastructure.persistence.mapper import SnapshotMapper  # noqa: E402
from app.infrastructure.persistence.search_mapping import (  # noqa: E402
    search_text,
    to_search_document,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (  # noqa: E402
    SQLAlchemyObjectRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier  # noqa: E402
from app.infrastructure.vector_db.fake import FakeVectorRepository  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1/assistant"


@pytest.fixture()
def harness():
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
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    repo = SQLAlchemyObjectRepository(session)
    vectors = FakeVectorRepository()
    embedder = HashingEmbedder()
    with TestClient(app) as client:
        yield client, repo, session, vectors, embedder
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _index(session, vectors, embedder, *objects: UniversalObject) -> None:
    for obj in objects:
        SQLAlchemyObjectRepository(session).save(obj)
    SearchIndexApplier(session).apply_pending()
    for obj in objects:
        snap = SnapshotMapper.to_snapshot(obj)
        doc = to_search_document(snap)
        vectors.upsert(
            VectorDocument(
                object_id=doc.object_id,
                object_type=doc.object_type,
                title=doc.title,
                metadata_text=doc.metadata_text,
                version=doc.version,
                vector=tuple(embedder.embed(search_text(snap))),
            )
        )


def _conversation(repo, *, question="find quantum", answer="The quantum answer.",
                  citations=(), review=None) -> UniversalObject:
    conv = create_conversation_object(repo, "New conversation", "u:1", title_auto=True)
    append_message(conv, "user", question, None)
    append_message(
        conv,
        "assistant",
        answer,
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question=question,
            summary=answer, sources=["llm"], citations=list(citations),
        ),
    )
    if review is not None:
        conv.set_metadata(
            MetadataEntry(
                "assistant.review_status", review,
                MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
            ),
            actor="system",
        )
    repo.save(conv)
    return conv


def _citation() -> AssistantCitation:
    return AssistantCitation(
        number=1,
        object_id="obj:document:1",
        object_type="document",
        title="Quantum Mechanics Notes",
        sources=("search",),
        version=1,
        score=0.9,
    )


# -------------------------------------------------------------------- auth
def test_memory_recall_requires_authentication(harness):
    client, _, _, _, _ = harness
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get(f"{API}/memory/recall", params={"q": "quantum"}).status_code == 401


# ------------------------------------------------------------------- recall
def test_memory_recall_empty_on_an_empty_world(harness):
    client, _, _, _, _ = harness
    r = client.get(f"{API}/memory/recall", params={"q": "find quantum"})
    assert r.status_code == 200
    assert r.json() == {"conversations": [], "knowledge": [], "search_count": 0, "graph_count": 0}


def test_memory_recall_returns_conversations_with_citations(harness):
    client, repo, session, vectors, embedder = harness
    conv = _conversation(repo, citations=[_citation()])
    _index(session, vectors, embedder, conv)

    r = client.get(f"{API}/memory/recall", params={"q": "find quantum"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["conversations"]) == 1
    item = body["conversations"][0]
    assert item["conversation_id"] == str(conv.id)
    assert item["question"] == "find quantum"
    assert item["answer"] == "The quantum answer."
    assert item["citations"] == [
        {
            "number": 1,
            "object_id": "obj:document:1",
            "object_type": "document",
            "title": "Quantum Mechanics Notes",
            "sources": ["search"],
            "version": 1,
            "score": 0.9,
        }
    ]
    assert item["review_status"] == ""
    assert item["last_message_at"]


def test_memory_recall_hides_pending_answers(harness):
    client, repo, session, vectors, embedder = harness
    conv = _conversation(repo, citations=[_citation()], review="pending")
    _index(session, vectors, embedder, conv)

    r = client.get(f"{API}/memory/recall", params={"q": "find quantum"})
    item = r.json()["conversations"][0]
    assert item["review_status"] == "pending"
    assert item["answer"] == ""
    assert item["citations"] == []


def test_memory_recall_graph_leg_returns_knowledge(harness):
    client, repo, session, vectors, embedder = harness
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Lab Notes", created_by="f:1")
    conv = _conversation(repo)
    conv.add_relationship(
        ObjectId(str(doc.id)), RelationshipKind.RELATED_TO,
        provenance=Provenance.ASSERTED, actor="system",
    )
    _index(session, vectors, embedder, conv, doc)

    r = client.get(f"{API}/memory/recall", params={"q": "find quantum"})
    body = r.json()
    assert len(body["conversations"]) == 1
    assert any(
        k["object_id"] == str(doc.id) and k["object_type"] == "document"
        for k in body["knowledge"]
    )
    assert body["graph_count"] >= 1


def test_memory_recall_validation_and_bounds(harness):
    client, _, _, _, _ = harness
    assert client.get(f"{API}/memory/recall").status_code == 422  # q required
    assert client.get(f"{API}/memory/recall", params={"q": ""}).status_code == 422
    assert client.get(
        f"{API}/memory/recall", params={"q": "x" * 201}
    ).status_code == 422
    assert client.get(
        f"{API}/memory/recall", params={"q": "quantum", "limit": 0}
    ).status_code == 422
    assert client.get(
        f"{API}/memory/recall", params={"q": "quantum", "limit": 51}
    ).status_code == 422
