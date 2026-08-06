"""Unit tests for assistant memory & knowledge retrieval (Sprint-8 M1).

Covers the memory recall over the REAL retrieval pipeline (search index +
graph runtime + fusion, all R4-gated): persisted-conversation recall,
conversation recall by content, citation preservation from the stored
answer payload, the review gate (pending/rejected answers never leak
into memory), the graph-aware knowledge leg, permission filtering,
deterministic ordering/limits, and the backward-compatible object_type
passthrough on the retrieval service.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.assistant.verifier import AnswerVerifier
from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantCitation,
    REVIEW_APPROVED,
    REVIEW_PENDING,
)
from app.application.services.assistant_memory import AssistantMemoryService
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import AssistantReviewQueue
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.assistant.helpers import (
    append_message,
    create_conversation_object,
    get_conversation_object,
)
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import (
    search_text,
    to_search_document,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.vector_db.fake import FakeVectorRepository


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
def world(db):
    """Real repository + retrieval stack + indexed vector store."""
    repo = SQLAlchemyObjectRepository(db)
    vectors = FakeVectorRepository()
    embedder = HashingEmbedder()
    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator(),
        vector_repository=vectors, embedder=embedder,
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    retrieval = AssistantRetrievalService(search, graph)
    memory = AssistantMemoryService(repo, retrieval)

    def index(*objects: UniversalObject) -> None:
        # The repository auto-emits pending domain events as durable outbox
        # rows (deduped by event_id), the applier drains them into the
        # lexical projection, and the vector store gets the same
        # deterministic document — the real indexing path end to end.
        for obj in objects:
            repo.save(obj)
        SearchIndexApplier(db).apply_pending()
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

    return {
        "db": db,
        "repo": repo,
        "memory": memory,
        "retrieval": retrieval,
        "index": index,
    }


def _asker() -> UniversalObject:
    asker = UniversalObject.create(
        ObjectType.USER, "eval", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:eval-0001"),
    )
    asker.pop_domain_events()
    return asker


def _citations() -> tuple[AssistantCitation, ...]:
    return (
        AssistantCitation(
            number=1,
            object_id="obj:document:1",
            object_type="document",
            title="Quantum Mechanics Notes",
            sources=("search",),
            version=1,
            score=0.9,
        ),
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


def test_recall_finds_persisted_conversation_memory(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    conv = _conversation(repo, citations=_citations())
    index(conv)

    recall = memory.recall("find quantum", asker)
    assert len(recall.conversations) == 1
    item = recall.conversations[0]
    assert item.conversation_id == str(conv.id)
    assert item.title == conv.title
    assert item.question == "find quantum"
    assert item.answer == "The quantum answer."
    assert item.score > 0.0
    assert "search" in item.sources
    assert item.last_message_at


def test_recall_preserves_citations_from_the_stored_answer(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    conv = _conversation(repo, citations=_citations())
    index(conv)

    item = memory.recall("find quantum", asker).conversations[0]
    assert item.citations == _citations()
    assert item.citations[0].number == 1
    assert item.citations[0].title == "Quantum Mechanics Notes"


def test_recall_is_empty_when_nothing_is_indexed(world):
    memory, index = world["memory"], world["index"]
    asker = _asker()
    index(asker)  # the only indexed object is the asker — no memory exists

    recall = memory.recall("find quantum", asker)
    assert recall.conversations == ()
    assert recall.knowledge == ()
    assert recall.search_count == 0


def test_recall_hides_pending_and_rejected_answers(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    pending = _conversation(repo, review=REVIEW_PENDING, citations=_citations())
    index(pending)

    item = memory.recall("find quantum", asker).conversations[0]
    assert item.review_status == REVIEW_PENDING
    assert item.answer == ""  # unapproved content never leaks
    assert item.citations == ()
    assert item.question == "find quantum"  # the question itself is visible

    # After approval the same memory carries the answer and citations.
    AssistantReviewQueue(repo).approve(str(pending.id))
    index(get_conversation_object(repo, str(pending.id)))
    item = memory.recall("find quantum", asker).conversations[0]
    assert item.review_status == REVIEW_APPROVED
    assert item.answer == "The quantum answer."
    assert item.citations == _citations()


def test_recall_graph_leg_discovers_related_knowledge(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Lab Notes", created_by="f:1")
    conv = _conversation(repo)
    conv.add_relationship(
        ObjectId(str(doc.id)), RelationshipKind.RELATED_TO,
        provenance=Provenance.ASSERTED, actor="system",
    )
    index(conv, doc)

    recall = memory.recall("find quantum", asker)
    assert len(recall.conversations) == 1
    assert any(
        k.object_id == str(doc.id) and k.object_type == "document"
        for k in recall.knowledge
    )
    assert recall.graph_count >= 1


def test_recall_respects_permission_filtering(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    # A conversation restricted to another reader must not be recalled.
    restricted = _conversation(repo)
    restricted.set_metadata(
        MetadataEntry(
            "acl.readers", '["obj:user:someone-else"]',
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    index(restricted)

    assert memory.recall("find quantum", asker).conversations == ()


def test_recall_is_deterministic_and_bounded(world):
    repo, memory, index = world["repo"], world["memory"], world["index"]
    asker = _asker()
    index(asker)
    for title in ("A", "B", "C"):
        conv = _conversation(repo, question=f"find quantum {title}")
        index(conv)

    first = memory.recall("find quantum", asker, limit=10)
    second = memory.recall("find quantum", asker, limit=10)
    assert [c.conversation_id for c in first.conversations] == [
        c.conversation_id for c in second.conversations
    ]
    assert len(memory.recall("find quantum", asker, limit=2).conversations) == 2


def test_retrieval_object_type_passthrough_is_backward_compatible(world):
    repo, retrieval, index = world["repo"], world["retrieval"], world["index"]
    asker = _asker()
    index(asker)
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Mechanics Notes", created_by="f:1")
    conv = _conversation(repo)
    index(conv, doc)

    # ``None`` (the pre-M1 default) retrieves every type (the asker is a
    # searchable user object too).
    all_items = retrieval.retrieve("find quantum", asker).items
    all_types = {i.object_type for i in all_items}
    assert "ai_conversation" in all_types and "document" in all_types

    # Narrowed to conversations, only the conversation comes back.
    conv_items = retrieval.retrieve(
        "find quantum", asker, object_type=ObjectType.AI_CONVERSATION.value
    ).items
    assert {i.object_type for i in conv_items} == {"ai_conversation"}
    assert conv_items[0].object_id == str(conv.id)
