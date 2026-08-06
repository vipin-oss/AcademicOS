"""Integration tests for the S6 M1 assistant pipeline (Phases 3-5).

The orchestrated AskQuestionUseCase (retrieval + context builder wired)
feeds the provider a permission-filtered, budgeted context envelope;
conversation persistence, title generation and follow-ups reuse the
existing helpers; restricted objects never reach the answer.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.providers import RuleBasedAssistantProvider
from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos.assistant import (
    AskQuestionInput,
    AssistantAnswerOutput,
    AssistantContext,
)
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.use_cases.assistant.helpers import read_messages
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
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
def repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _save_with_events(repo: SQLAlchemyObjectRepository, obj: UniversalObject) -> None:
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(event) for event in events])


def _index(db, repo, *objects: UniversalObject) -> FakeVectorRepository:
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    for obj in objects:
        _save_with_events(repo, obj)
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
    return vectors


def _user() -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


class CapturingProvider:
    """Deterministic provider that records the context it receives."""

    name = "capture-v1"

    def __init__(self) -> None:
        self.received: list[AssistantContext | None] = []
        self.seen_titles: list[list[str]] = []

    def answer(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
    ) -> AssistantAnswerOutput:
        self.received.append(context)
        self.seen_titles.append([item.title for item in (context.retrieved if context else [])])
        return AssistantAnswerOutput(
            intent="knowledge_search",
            intent_label="Knowledge search",
            question=question,
            summary="Grounded answer.",
            sources=["hybrid_search"],
        )


def _wired_use_case(db, repo, vectors, provider=None):
    provider = provider or CapturingProvider()
    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db),
        repo,
        ObjectPermissionEvaluator(),
        vector_repository=vectors,
        embedder=HashingEmbedder(),
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    retrieval = AssistantRetrievalService(search, graph)
    return AskQuestionUseCase(
        repo, provider, retrieval=retrieval, context_builder=AssistantContextBuilder()
    ), provider


def _ask(use_case, question: str, conversation_id: str | None = None):
    return use_case.execute(
        AskQuestionCommand(
            input=AskQuestionInput(
                question=question,
                asked_by="obj:user:alice-0001",
                conversation_id=conversation_id,
            )
        )
    )


def test_new_conversation_builds_context_and_persists(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    vectors = _index(db, repo, doc, _user())
    use_case, provider = _wired_use_case(db, repo, vectors)

    out = _ask(use_case, "find quantum")
    assert out.conversation.message_count == 2
    assert len(provider.received) == 1
    context = provider.received[0]
    assert context is not None
    assert context.question == "find quantum"
    assert any(item.title == "Quantum Paper" for item in context.retrieved)
    assert context.history == ()  # first turn: no history yet
    # Title generation reused: derived from the first question.
    assert out.conversation.title == "find quantum"


def test_follow_up_reuses_conversation_and_history(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    vectors = _index(db, repo, doc, _user())
    use_case, provider = _wired_use_case(db, repo, vectors)

    first = _ask(use_case, "find quantum")
    second = _ask(use_case, "tell me more", conversation_id=str(first.conversation.id))
    assert second.conversation.id == first.conversation.id
    assert second.conversation.message_count == 4
    # The follow-up context carries the prior turn's history.
    context = provider.received[1]
    assert context is not None
    assert [role for role, _c in context.history] == ["user", "assistant"]


def test_restricted_objects_never_reach_the_provider(db, repo):
    public = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Public", created_by="f:1")
    secret = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Secret", created_by="f:2")
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    vectors = _index(db, repo, public, secret, _user())
    use_case, provider = _wired_use_case(db, repo, vectors)

    _ask(use_case, "find quantum")
    # The provider only ever sees permitted items — the leak is impossible
    # before the prompt is even built.
    assert all("Secret" not in title for title in provider.seen_titles[0])


def test_graph_results_flow_into_the_provider_context(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    neighbor = UniversalObject.create(ObjectType.DOCUMENT, "Neighbor Notes", created_by="f:1")
    doc.add_relationship(neighbor.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors = _index(db, repo, doc, neighbor, _user())
    use_case, provider = _wired_use_case(db, repo, vectors)

    _ask(use_case, "find quantum")
    titles = provider.seen_titles[0]
    assert "Neighbor Notes" in titles  # the graph leg contributed


def test_rules_provider_knowledge_search_uses_context_cards(db, repo):
    """The production provider answers knowledge queries from the retrieval
    envelope when present (falling back to the scan otherwise)."""
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Context Document", created_by="f:1")
    vectors = _index(db, repo, doc, _user())
    provider = RuleBasedAssistantProvider(repo)
    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db),
        repo,
        ObjectPermissionEvaluator(),
        vector_repository=vectors,
        embedder=HashingEmbedder(),
    )
    retrieval = AssistantRetrievalService(search, GraphRuntimeService(repo, ObjectPermissionEvaluator()))
    use_case = AskQuestionUseCase(
        repo, provider, retrieval=retrieval, context_builder=AssistantContextBuilder()
    )

    out = _ask(use_case, "find context")
    assert out.answer.intent == "knowledge_search"
    card_titles = [card.title for card in out.answer.cards]
    assert "Context Document" in card_titles
    assert "hybrid_search" in out.answer.sources or "knowledge_graph" in out.answer.sources
    # The answer was persisted with its cards.
    messages = read_messages(repo.get_by_id(ObjectId(str(out.conversation.id))))
    assistant_payload = [p for _s, p in messages if p["role"] == "assistant"][0]
    assert assistant_payload["answer"]["cards"]
