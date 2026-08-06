"""Pipeline tests for the LLM provider integration (Sprint-6 M2 P4).

The full ask pipeline with the Prompt Builder wired: the built prompt
reaches the LLM transport, the LLM answer is persisted, a provider failure
degrades to the deterministic rules fallback without crashing, follow-ups
carry history into the prompt, and restricted objects never appear in the
prompt (the permission filter happens before prompt construction).
"""
from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos.assistant import AskQuestionInput
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
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
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


def _llm_chain(repo, handler) -> FallbackAssistantProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    primary = LlmAssistantProvider(
        client, model="test-model", base_url="http://llm.example",
        retry_attempts=2, retry_backoff_seconds=0,
    )
    fallback = RuleBasedAssistantProvider(
        repo, permission_evaluator=ObjectPermissionEvaluator()
    )
    return FallbackAssistantProvider(primary, fallback)


def _wired_use_case(db, repo, vectors, provider):
    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator(),
        vector_repository=vectors, embedder=HashingEmbedder(),
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    retrieval = AssistantRetrievalService(search, graph)
    return AskQuestionUseCase(
        repo,
        provider,
        retrieval=retrieval,
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
    )


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


def test_llm_receives_built_prompt_and_answer_persists(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    vectors = _index(db, repo, doc, _user())
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The LLM's grounded answer."}}]},
        )

    use_case = _wired_use_case(db, repo, vectors, _llm_chain(repo, handler))
    out = _ask(use_case, "find quantum")

    # The built prompt reached the transport with the provenance section.
    user_message = captured["body"]["messages"][1]["content"]
    assert "RETRIEVED CONTEXT" in user_message
    assert "Quantum Paper" in user_message
    assert "QUESTION:\nfind quantum" in user_message
    assert captured["body"]["messages"][0]["role"] == "system"

    # The LLM answer was persisted as the assistant message.
    assert out.answer.summary == "The LLM's grounded answer."
    assert out.answer.intent == "llm"
    assert out.conversation.message_count == 2
    messages = read_messages(repo.get_by_id(ObjectId(str(out.conversation.id))))
    assistant_payload = [p for _s, p in messages if p["role"] == "assistant"][0]
    assert assistant_payload["content"] == "The LLM's grounded answer."


def test_llm_failure_falls_back_and_persists(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    vectors = _index(db, repo, doc, _user())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    use_case = _wired_use_case(db, repo, vectors, _llm_chain(repo, handler))
    out = _ask(use_case, "find quantum")

    # Deterministic fallback answered; the conversation still persisted.
    assert out.answer.intent == "knowledge_search"
    assert out.answer.summary
    assert out.conversation.message_count == 2
    assert out.answer.sources  # rules-provider sources


def test_follow_up_carries_history_into_the_prompt(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    vectors = _index(db, repo, doc, _user())
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    use_case = _wired_use_case(db, repo, vectors, _llm_chain(repo, handler))
    first = _ask(use_case, "find quantum")
    second = _ask(use_case, "tell me more", conversation_id=str(first.conversation.id))

    assert second.conversation.message_count == 4
    user_message = captured["body"]["messages"][1]["content"]
    assert "CONVERSATION HISTORY" in user_message
    assert "find quantum" in user_message  # the prior user turn is in history


def test_restricted_object_never_enters_the_prompt(db, repo):
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
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    use_case = _wired_use_case(db, repo, vectors, _llm_chain(repo, handler))
    _ask(use_case, "find quantum")
    user_message = captured["body"]["messages"][1]["content"]
    assert "Quantum Public" in user_message
    assert "Secret" not in user_message  # filtered before prompt construction


def test_graph_results_enter_the_prompt(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    neighbor = UniversalObject.create(ObjectType.DOCUMENT, "Neighbor Notes", created_by="f:1")
    doc.add_relationship(neighbor.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors = _index(db, repo, doc, neighbor, _user())
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    use_case = _wired_use_case(db, repo, vectors, _llm_chain(repo, handler))
    _ask(use_case, "find quantum")
    user_message = captured["body"]["messages"][1]["content"]
    assert "Neighbor Notes" in user_message  # the graph leg contributed


def _seed_asker(repo) -> None:
    """Persist the asker WITHOUT events so it is not indexed (the citation
    tests assert on the document citations alone)."""
    user = _user()
    user.pop_domain_events()
    repo.save(user)


# ------------------------------------------------------------- citations (M3)


def _wired_with_citations(db, repo, vectors, provider):
    from app.application.assistant.citations import CitationBuilder
    from app.application.assistant.verifier import AnswerVerifier

    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator(),
        vector_repository=vectors, embedder=HashingEmbedder(),
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    retrieval = AssistantRetrievalService(search, graph)
    return AskQuestionUseCase(
        repo,
        provider,
        retrieval=retrieval,
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
    )


def test_citations_reach_the_llm_request_and_answer(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(repo, handler))
    out = _ask(use_case, "find quantum")

    # The numbered evidence travels with the request.
    wire_citations = captured["body"]["citations"]
    assert len(wire_citations) == 1
    assert wire_citations[0]["object_id"] == str(doc.id)
    assert wire_citations[0]["number"] == 1
    assert "sources" in wire_citations[0]
    # The prompt carries the [n] marker.
    assert "[1]" in captured["body"]["messages"][1]["content"]
    # The answer carries the verified citation + evidence card.
    assert len(out.answer.citations) == 1
    assert out.answer.citations[0].object_id == str(doc.id)
    assert out.answer.citations[0].number == 1
    assert out.answer.cards  # evidence cards filled the empty cards slot
    assert out.answer.cards[0].href.endswith(str(doc.id))


def test_citations_persist_and_reload(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )
    ))
    out = _ask(use_case, "find quantum")

    # Reload the conversation: the persisted answer reconstructs citations.
    messages = read_messages(repo.get_by_id(ObjectId(str(out.conversation.id))))
    assistant_payload = [p for _s, p in messages if p["role"] == "assistant"][0]
    raw_citations = assistant_payload["answer"]["citations"]
    assert len(raw_citations) == 1
    assert raw_citations[0]["object_id"] == str(doc.id)


def test_restricted_object_never_cited(db, repo):
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
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(repo, handler))
    out = _ask(use_case, "find quantum")
    # The restricted object never reached the prompt or the citations.
    assert "Quantum Secret" not in captured["body"]["messages"][1]["content"]
    assert all(c.object_id != str(secret.id) for c in out.answer.citations)


def test_deleted_object_citation_dropped_before_attach(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Doomed Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )
    ))
    # Delete the object AFTER retrieval but BEFORE the provider returns:
    # the verifier must drop the citation (the object no longer exists).
    repo.delete(doc.id)
    out = _ask(use_case, "find doomed")
    assert out.answer.citations == []
