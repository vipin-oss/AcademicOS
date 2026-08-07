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

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.application.assistant.verifier import AnswerVerifier
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


# ------------------------------------------------------------- streaming (M4)


def _sse_content(*chunks: str) -> bytes:
    import json as _json

    lines = [
        f"data: {_json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks
    ]
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


def test_stream_yields_tokens_then_verified_completion(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(200, content=_sse_content("The", " answer", "."))
    ))

    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))

    tokens = [e for e in events if e["event"] == "token"]
    assert [t["data"]["delta"] for t in tokens] == ["The", " answer", "."]
    completions = [e for e in events if e["event"] == "completion"]
    assert len(completions) == 1
    data = completions[0]["data"]
    assert data["answer"]["summary"] == "The answer."
    assert data["answer"]["intent"] == "llm"
    # Citations verified + evidence cards present.
    assert len(data["answer"]["citations"]) == 1
    assert data["answer"]["citations"][0]["object_id"] == str(doc.id)
    assert data["answer"]["cards"]
    assert data["conversation"]["message_count"] == 2


def test_stream_persists_only_final_verified_answer(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(200, content=_sse_content("Final", " answer"))
    ))

    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))
    completion = [e for e in events if e["event"] == "completion"][0]
    conv_id = completion["data"]["conversation"]["id"]

    # The stored assistant message matches the streamed answer exactly —
    # no partial tokens were persisted, only the final verified text.
    messages = read_messages(repo.get_by_id(ObjectId(conv_id)))
    assistant = [p for _s, p in messages if p["role"] == "assistant"][0]
    assert assistant["content"] == "Final answer"
    assert assistant["answer"]["summary"] == "Final answer"
    assert len(messages) == 2


def test_stream_cancellation_persists_nothing(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(200, content=_sse_content("a", "b", "c"))
    ))

    gen = use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    )
    first = next(gen)
    assert first["event"] == "token"
    gen.close()  # client disconnect mid-stream

    # Nothing was persisted: no messages were appended anywhere.
    conversations = repo.find_by_type(ObjectType.AI_CONVERSATION)
    for conv in conversations:
        assert read_messages(conv) == []


def test_stream_error_event_persists_nothing(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    # A bare LLM provider with NO fallback chain: the error surfaces.
    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    from app.infrastructure.llm.llm_provider import LlmAssistantProvider

    bare = LlmAssistantProvider(
        client, model="m", base_url="http://llm.example",
        retry_attempts=1, retry_backoff_seconds=0,
    )
    use_case = _wired_with_citations(db, repo, vectors, bare)

    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))
    assert events[-1]["event"] == "error"
    assert "unreachable" in events[-1]["data"]["message"]
    conversations = repo.find_by_type(ObjectType.AI_CONVERSATION)
    for conv in conversations:
        assert read_messages(conv) == []  # no partial persistence


def test_stream_chain_falls_back_to_rules_completion(db, repo):
    """Provider failure mid-stream -> the chain yields a deterministic
    rules completion (no error event, conversation persisted)."""
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)

    class BoomStream:
        name = "boom"

        def stream(self, question, asked_by, *, context=None, prompt=None):
            yield {"type": "token", "delta": "partial"}
            raise RuntimeError("connection lost")

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            from app.application.dtos.assistant import AssistantAnswerOutput

            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="deterministic fallback", sources=["rules"],
            )

    from app.application.assistant.providers import FallbackAssistantProvider

    use_case = _wired_with_citations(
        db, repo, vectors, FallbackAssistantProvider(BoomStream(), Fallback())
    )
    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))
    assert [e["event"] for e in events] == ["token", "completion"]
    assert events[0]["data"]["delta"] == "partial"
    assert events[1]["data"]["answer"]["summary"] == "deterministic fallback"
    assert events[1]["data"]["conversation"]["message_count"] == 2  # persisted


def test_stream_rules_provider_single_token_completion(db, repo):
    """Without a stream capability the pipeline yields one token carrying
    the whole deterministic answer, then the completion."""
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    from app.application.assistant.providers import RuleBasedAssistantProvider

    rules = RuleBasedAssistantProvider(repo, permission_evaluator=ObjectPermissionEvaluator())
    use_case = _wired_with_citations(db, repo, vectors, rules)

    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))
    assert [e["event"] for e in events] == ["token", "completion"]
    assert events[0]["data"]["delta"] == events[1]["data"]["answer"]["summary"]
    assert events[1]["data"]["answer"]["intent"] == "knowledge_search"
    assert events[1]["data"]["conversation"]["message_count"] == 2


def test_stream_follow_up_on_existing_conversation(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    use_case = _wired_with_citations(db, repo, vectors, _llm_chain(
        repo, lambda request: httpx.Response(200, content=_sse_content("First", " answer"))
    ))

    first = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001"
        ))
    ))
    conv_id = [e for e in first if e["event"] == "completion"][0]["data"]["conversation"]["id"]

    second = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="tell me more", asked_by="obj:user:alice-0001", conversation_id=conv_id
        ))
    ))
    completion = [e for e in second if e["event"] == "completion"][0]["data"]
    assert completion["conversation"]["id"] == conv_id
    assert completion["conversation"]["message_count"] == 4  # follow-up persisted
    assert completion["answer"]["summary"] == "First answer"


# ----------------------------------------------------- model selection (M2)


def _ai_core_for_tests(client):
    """An AI Core with two OpenAI-compatible providers (main/alt) sharing a
    MockTransport client - the AI-Core authority for selection tests."""
    from app.application.ai.config import AiConfigView
    from app.application.ai.core import AiCore
    from app.application.ai.providers.registry import ProviderRegistry
    from app.application.dtos.ai import ProviderConfig
    from app.infrastructure.ai.llm.openai import OpenAIProvider

    def _gw(pid, model, base):
        return OpenAIProvider(
            ProviderConfig(provider_id=pid, kind="openai", model=model, base_url=base),
            client=client, retry_attempts=2, retry_backoff_seconds=0,
        )

    gateways = {
        "main": _gw("main", "model-main", "http://a/v1"),
        "alt": _gw("alt", "model-alt", "http://b/v1"),
    }
    ai_cfg = AiConfigView(
        enabled=True, default_provider="main", default_model="",
        temperature=0.0, max_tokens=2048, timeout_seconds=30.0, streaming_enabled=True,
        feature_flags={"chat": False, "rag": False, "memory": False, "agents": False,
                       "document_understanding": False, "streaming": True},
    )
    return AiCore(
        registry=ProviderRegistry(), gateways=gateways, config=ai_cfg, default_provider="main"
    )


def _wired_with_registry(db, repo, vectors, handler):
    """The full pipeline wired with AI-Core provider selection (ADR-001)."""
    from app.infrastructure.assistant.provider_factory import build_assistant_provider

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ai_core = _ai_core_for_tests(client)

    def factory(provider_id, repository, *, fallback=None):
        return build_assistant_provider(
            ai_core.gateway(provider_id), repository, fallback=fallback
        )

    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator(),
        vector_repository=vectors, embedder=HashingEmbedder(),
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    retrieval = AssistantRetrievalService(search, graph)
    return AskQuestionUseCase(
        repo,
        None,  # unused when the AI Core selection path is active
        retrieval=retrieval,
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        ai_core=ai_core,
        provider_factory=factory,
    )


def _ask_with_model(use_case, question: str, model_id: str | None = None, conversation_id: str | None = None):
    return use_case.execute(
        AskQuestionCommand(input=AskQuestionInput(
            question=question, asked_by="obj:user:alice-0001",
            conversation_id=conversation_id, model_id=model_id,
        ))
    )


def test_conversation_pins_default_model_and_persists(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "a"}}]})

    use_case = _wired_with_registry(db, repo, vectors, handler)
    first = _ask_with_model(use_case, "find quantum")
    # Default model was used and pinned on the conversation.
    assert captured["model"] == "model-main"
    conv_id = str(first.conversation.id)
    stored = repo.get_by_id(ObjectId(conv_id))
    assert stored.metadata.get_value("assistant.provider_id") == "main"

    # Follow-up WITHOUT an override reuses the pin.
    captured.clear()
    _ask_with_model(use_case, "find quantum", conversation_id=conv_id)
    assert captured["model"] == "model-main"


def test_request_override_replaces_model_and_repins(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "a"}}]})

    use_case = _wired_with_registry(db, repo, vectors, handler)
    first = _ask_with_model(use_case, "find quantum", model_id="alt")
    assert captured["model"] == "model-alt"
    conv_id = str(first.conversation.id)
    stored = repo.get_by_id(ObjectId(conv_id))
    assert stored.metadata.get_value("assistant.provider_id") == "alt"  # re-pinned

    # Follow-up without override now uses the new pin.
    captured.clear()
    _ask_with_model(use_case, "find quantum", conversation_id=conv_id)
    assert captured["model"] == "model-alt"


def test_stream_uses_identical_selection(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(
            200, content=_sse_content("streamed", " answer")
        )

    use_case = _wired_with_registry(db, repo, vectors, handler)
    events = list(use_case.stream(
        AskQuestionCommand(input=AskQuestionInput(
            question="find quantum", asked_by="obj:user:alice-0001", model_id="alt"
        ))
    ))
    assert captured["model"] == "model-alt"
    completion = [e for e in events if e["event"] == "completion"][0]
    assert completion["data"]["answer"]["summary"] == "streamed answer"


def test_invalid_model_id_is_rejected(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed_asker(repo)
    vectors = _index(db, repo, doc)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "a"}}]})

    use_case = _wired_with_registry(db, repo, vectors, handler)
    from app.application.ai.errors import UnknownProviderError

    with pytest.raises(UnknownProviderError):
        _ask_with_model(use_case, "find quantum", model_id="ghost")
