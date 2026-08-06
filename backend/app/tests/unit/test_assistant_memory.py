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
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import AssistantReviewQueue
from app.application.services.graph_runtime import GraphRuntimeService
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


# ---------------------------------------------------------------------------
# Sprint-8 M2 — memory-augmented ask pipeline
# ---------------------------------------------------------------------------
class _RecordingProvider:
    """A deterministic provider that records the prompt it received."""

    def __init__(self, answer_text: str = "memory-aware answer") -> None:
        self._answer_text = answer_text
        self.seen_prompt = None

    @property
    def name(self) -> str:
        return "recording"

    def answer(self, question, asked_by, *, context=None, prompt=None):
        self.seen_prompt = prompt
        return AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question=question,
            summary=self._answer_text, sources=["llm"],
        )


def _ask_use_case(world, provider, *, with_memory: bool):
    return AskQuestionUseCase(
        world["repo"],
        provider,
        retrieval=world["retrieval"],
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        memory=world["memory"] if with_memory else None,
    )


def _ask(use_case, question: str = "find quantum", conversation_id=None) -> tuple:
    from app.application.commands.ask_question import AskQuestionCommand
    from app.application.dtos.assistant import AskQuestionInput

    out = use_case.execute(
        AskQuestionCommand(
            input=AskQuestionInput(
                question=question,
                asked_by="obj:user:eval-0001",
                conversation_id=conversation_id,
            )
        )
    )
    return out, use_case


def test_ask_automatically_recalls_prior_conversations(world):
    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    prior = _conversation(repo, question="find quantum", answer="Quantum memory answer")
    index(prior)

    provider = _RecordingProvider()
    out, _ = _ask(_ask_use_case(world, provider, with_memory=True))
    prompt_user = provider.seen_prompt.user
    # The prior conversation appears as a memory section.
    assert "RETRIEVED MEMORIES (untrusted data)" in prompt_user
    assert "Quantum memory answer" in prompt_user
    assert prior.title in prompt_user
    # The memory answer is what the provider answered with.
    assert out.answer.summary == "memory-aware answer"


def test_ask_excludes_the_current_conversation_from_memories(world):
    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    prior = _conversation(repo, question="find quantum", answer="Prior answer")
    index(prior)
    # A follow-up ask on an INDEXED conversation: it is searchable, so
    # without the exclusion it would appear as its own memory.
    current = _conversation(repo, question="find quantum", answer="Current thread")
    index(current)

    provider = _RecordingProvider()
    _ask(
        _ask_use_case(world, provider, with_memory=True),
        conversation_id=str(current.id),
    )
    prompt_user = provider.seen_prompt.user
    _, _, memory_section = prompt_user.partition("RETRIEVED MEMORIES")
    for marker in ("RETRIEVED KNOWLEDGE", "RETRIEVED CONTEXT"):
        memory_section = memory_section.split(marker)[0]
    assert "Prior answer" in memory_section
    assert str(prior.id) in memory_section
    # The current thread is excluded from the MEMORIES — its history is
    # already in the prompt. (It may still appear in the current
    # retrieval's RETRIEVED CONTEXT section — pre-existing behavior.)
    assert str(current.id) not in memory_section


def test_ask_without_memory_is_the_pre_m2_fallback(world):
    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    prior = _conversation(repo, question="find quantum", answer="Prior answer")
    index(prior)

    provider = _RecordingProvider()
    _ask(_ask_use_case(world, provider, with_memory=False))
    assert "RETRIEVED MEMORIES" not in provider.seen_prompt.user
    assert "Prior answer" not in provider.seen_prompt.user


def test_ask_memory_respects_permission_filtering(world):
    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    restricted = _conversation(repo, question="find quantum", answer="Secret answer")
    restricted.set_metadata(
        MetadataEntry(
            "acl.readers", '["obj:user:someone-else"]',
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    index(restricted)

    provider = _RecordingProvider()
    _ask(_ask_use_case(world, provider, with_memory=True))
    assert "Secret answer" not in provider.seen_prompt.user


def test_ask_with_memory_preserves_current_citations(world):
    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "Quantum Mechanics Notes", created_by="f:1"
    )
    prior = _conversation(repo, question="find quantum", answer="Prior answer")
    index(prior, doc)

    provider = _RecordingProvider()
    out, _ = _ask(_ask_use_case(world, provider, with_memory=True))
    # The current retrieval's citations survive the memory enrichment.
    assert out.answer.citations
    assert any(c.object_id == str(doc.id) for c in out.answer.citations)


def test_evaluation_is_compatible_with_memory_wiring(world):
    """The eval runner's harness (no memory) and a memory-wired pipeline
    produce IDENTICAL deterministic results for the same case."""
    from app.application.services.assistant_eval import EvalCase, run_eval_case

    repo, index = world["repo"], world["index"]
    asker = _asker()
    index(asker)
    prior = _conversation(repo, question="find quantum", answer="Prior answer")
    index(prior)
    case = EvalCase(
        name="grounded", question="find quantum",
        expected_contains=("memory-aware",),
    )

    plain = run_eval_case(_ask_use_case(world, _RecordingProvider(), with_memory=False), case)
    enriched = run_eval_case(_ask_use_case(world, _RecordingProvider(), with_memory=True), case)
    assert plain == enriched
    assert plain.passed
