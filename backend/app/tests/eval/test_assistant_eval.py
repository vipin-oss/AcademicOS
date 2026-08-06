"""Assistant evaluation suite (Sprint-7 M1) — reproducible by construction.

Every case runs the REAL pipeline (retrieval, context, prompt, provider,
citations, verification, persistence) with a deterministic fake LLM
transport, so the same case always produces the same result. The eval
harness is deliberately the same shape the model registry will drive:
inject a provider, run cases, judge deterministically.
"""
from __future__ import annotations

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
from app.application.services.assistant_eval import (
    EvalCase,
    run_eval_case,
    run_eval_suite,
)
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
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


def _eval_use_case(db, repo, vectors, provider) -> AskQuestionUseCase:
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


def _fake_llm_chain(repo, answer_text: str) -> FallbackAssistantProvider:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": answer_text}}]}
            )
        )
    )
    primary = LlmAssistantProvider(
        client, model="eval-model", base_url="http://eval.example",
        retry_attempts=2, retry_backoff_seconds=0,
    )
    fallback = RuleBasedAssistantProvider(
        repo, permission_evaluator=ObjectPermissionEvaluator()
    )
    return FallbackAssistantProvider(primary, fallback)


def _seed_world(db, repo) -> FakeVectorRepository:
    """One document + the eval asker; both indexed (the asker must be a
    real, readable user for the pipeline to retrieve)."""
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Mechanics Notes", created_by="f:1")
    asker = UniversalObject.create(
        ObjectType.USER, "eval", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:eval-0001"),
    )
    asker.pop_domain_events()
    repo.save(asker)
    return _index(db, repo, doc)


def test_eval_case_passes_when_grounded_answer_produced(db, repo):
    vectors = _seed_world(db, repo)
    use_case = _eval_use_case(db, repo, vectors, _fake_llm_chain(repo, "The answer is grounded."))

    result = run_eval_case(
        use_case,
        EvalCase(
            name="grounded",
            question="find quantum",
            expected_contains=("grounded",),
            expect_citations=True,
        ),
    )
    assert result.passed, result.details
    assert result.details == ()


def test_eval_case_fails_when_expected_text_missing(db, repo):
    vectors = _seed_world(db, repo)
    use_case = _eval_use_case(db, repo, vectors, _fake_llm_chain(repo, "unrelated text"))

    result = run_eval_case(
        use_case,
        EvalCase(name="grounded", question="find quantum", expected_contains=("grounded",)),
    )
    assert not result.passed
    assert any("missing" in d for d in result.details)


def test_eval_case_fails_when_citations_missing(db, repo):
    """With an EMPTY world (no retrievable documents) the answer carries no
    citations, so an expect_citations case must fail."""
    # Only the asker exists; nothing is retrievable.
    asker = UniversalObject.create(
        ObjectType.USER, "eval", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:eval-0001"),
    )
    asker.pop_domain_events()
    repo.save(asker)
    vectors = FakeVectorRepository()
    use_case = _eval_use_case(db, repo, vectors, _fake_llm_chain(repo, "no citations here"))

    result = run_eval_case(
        use_case,
        EvalCase(
            name="cites", question="find quantum",
            expected_contains=("no citations",), expect_citations=True,
        ),
    )
    assert not result.passed
    assert any("citations" in d for d in result.details)


def test_eval_suite_reports_counts_and_is_reproducible(db, repo):
    vectors = _seed_world(db, repo)
    use_case = _eval_use_case(db, repo, vectors, _fake_llm_chain(repo, "Grounded answer"))

    cases = [
        EvalCase(name="pass-1", question="find quantum", expected_contains=("Grounded",), expect_citations=True),
        EvalCase(name="pass-2", question="find quantum", expected_contains=("answer",)),
        EvalCase(name="fail-1", question="find quantum", expected_contains=("missing-text",)),
    ]
    results, passed = run_eval_suite(use_case, cases)
    assert passed == 2
    assert [r.name for r in results if r.passed] == ["pass-1", "pass-2"]

    # Reproducible: a fresh pipeline over the same world yields the same
    # outcome for every case.
    again, passed_again = run_eval_suite(use_case, cases)
    assert passed_again == passed
    assert [r.passed for r in again] == [r.passed for r in results]
