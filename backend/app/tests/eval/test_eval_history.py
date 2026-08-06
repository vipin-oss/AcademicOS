"""Evaluation persistence, benchmark history & quality tracking (Sprint-7 M3).

Covers the durable ``eval_runs`` records: store round-trips, per-model
history ordering, record invariants, run-to-run comparison (regression
detection), deterministic replay, failed/partial runs, and backward
compatibility of the runner when no history is wired.
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
    EvalResult,
    EvalRun,
    EvaluationHistory,
    run_eval_suite_across_models,
)
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.model_registry import (
    PROVIDER_KIND_RULES,
    ModelRegistry,
    ModelSpec,
)
from app.application.services.outbox import to_outbox_row
from app.application.services.prompt_registry import (
    DEFAULT_PROMPT_ID,
    PromptAsset,
    PromptRegistry,
)
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
from app.infrastructure.persistence.eval_run_store import SQLEvalRunStore
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
def store(db) -> SQLEvalRunStore:
    return SQLEvalRunStore(db)


@pytest.fixture()
def history(db, store) -> EvaluationHistory:
    return EvaluationHistory(store)


def _results(*names: str, failed: tuple[str, ...] = ()) -> tuple[EvalResult, ...]:
    return tuple(
        EvalResult(
            name=name,
            passed=name not in failed,
            details=("missing marker",) if name in failed else (),
        )
        for name in names
    )


def _run(
    *,
    run_id: str = "run-1",
    model_id: str = "main",
    model_version: str = "main-model",
    prompt_id: str = "assistant.default",
    prompt_version: int = 1,
    results: tuple[EvalResult, ...] | None = None,
    created_at: str = "2026-08-06T00:00:00+00:00",
) -> EvalRun:
    results = results if results is not None else _results("a", "b")
    return EvalRun(
        run_id=run_id,
        model_id=model_id,
        model_version=model_version,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        passed=sum(1 for r in results if r.passed),
        total=len(results),
        results=results,
        created_at=created_at,
    )


# ------------------------------------------------------------------ store
def test_run_round_trips_through_the_store(db, store):
    run = _run(results=_results("a", "b", "c", failed=("b",)))
    store.add(run)

    fetched = store.get("run-1")
    assert fetched == run
    assert fetched.passed == 2 and fetched.total == 3
    assert fetched.results[1].passed is False
    assert fetched.results[1].details == ("missing marker",)


def test_get_unknown_run_returns_none(db, store):
    assert store.get("no-such-run") is None
    assert store.latest_by_model("main") is None
    assert store.recent_by_model("main", 10) == []


def test_history_is_newest_first_with_deterministic_order(db, store):
    older = _run(run_id="r1", created_at="2026-08-06T10:00:00+00:00")
    middle = _run(run_id="r2", created_at="2026-08-06T11:00:00+00:00")
    newer = _run(run_id="r3", created_at="2026-08-06T12:00:00+00:00")
    store.add(older)
    store.add(newer)
    store.add(middle)

    recent = store.recent_by_model("main", 10)
    assert [r.run_id for r in recent] == ["r3", "r2", "r1"]
    assert store.latest_by_model("main").run_id == "r3"
    # Bounded by limit.
    assert [r.run_id for r in store.recent_by_model("main", 2)] == ["r3", "r2"]


def test_history_is_isolated_per_model(db, store):
    store.add(_run(run_id="r1", model_id="main"))
    store.add(_run(run_id="r2", model_id="alt"))

    assert store.latest_by_model("main").run_id == "r1"
    assert store.latest_by_model("alt").run_id == "r2"
    assert store.latest_by_model("nope") is None
    assert store.recent_by_model("main", 10) == [store.get("r1")]


def test_history_lists_runs_across_all_models_newest_first(db, store, history):
    store.add(_run(run_id="a1", model_id="main", created_at="2026-08-06T09:00:00+00:00"))
    store.add(_run(run_id="b1", model_id="alt", created_at="2026-08-06T10:00:00+00:00"))
    store.add(_run(run_id="a2", model_id="main", created_at="2026-08-06T11:00:00+00:00"))

    assert [r.run_id for r in store.recent(10)] == ["a2", "b1", "a1"]
    assert [r.run_id for r in store.recent(2)] == ["a2", "b1"]
    # The service exposes the same list query.
    assert [r.run_id for r in history.recent_all(10)] == ["a2", "b1", "a1"]
    assert history.recent_all(0) == []


def test_run_record_validates_invariants(db, store):
    results = _results("a", "b")
    with pytest.raises(ValueError, match="passed"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=3, total=2, results=results, created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="exactly one entry"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=1, total=2, results=results[:1], created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="names must be unique"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=2, total=2,
            results=_results("a", "a"), created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="match the recorded results"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=0, total=2, results=results, created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="prompt_version"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=0,
            passed=2, total=2, results=results, created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="identity"):
        EvalRun(
            run_id="x", model_id="", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=2, total=2, results=results, created_at="2026-08-06T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="created_at"):
        EvalRun(
            run_id="x", model_id="main", model_version="main-model",
            prompt_id="assistant.default", prompt_version=1,
            passed=2, total=2, results=results, created_at="",
        )


# ---------------------------------------------------------------- history
def test_record_run_persists_and_returns_the_durable_record(history):
    run = history.record_run(
        model_id="main",
        model_version="main-model",
        prompt_id="assistant.default",
        prompt_version=3,
        results=_results("a", "b", "c", failed=("c",)),
    )
    assert history.get(run.run_id) == run
    assert run.passed == 2 and run.total == 3
    assert run.created_at  # evaluation timestamp recorded
    assert run.results[2].details == ("missing marker",)
    # Each recorded run gets a fresh identity.
    another = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=3, results=_results("a"),
    )
    assert another.run_id != run.run_id


def test_history_queries_via_the_service(history):
    first = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a"),
    )
    second = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a"),
    )
    assert history.latest("main").run_id == second.run_id
    assert [r.run_id for r in history.recent("main", 10)] == [
        second.run_id, first.run_id,
    ]
    assert history.latest("other") is None


# ------------------------------------------------------------- comparison
def test_compare_reports_regressions_fixes_and_stable(history):
    base = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1,
        results=_results("a", "b", "c", failed=("c",)),
    )
    candidate = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1,
        results=_results("a", "b", "c", failed=("a",)),
    )
    comparison = history.compare(base, candidate)
    assert comparison.regressions == ("a",)
    assert comparison.fixes == ("c",)
    assert comparison.stable_passes == ("b",)
    assert comparison.stable_failures == ()
    assert comparison.has_regressions
    assert comparison.base_passed == 2
    assert comparison.candidate_passed == 2
    assert comparison.total == 3
    assert comparison.base_run_id == base.run_id
    assert comparison.candidate_run_id == candidate.run_id


def test_compare_rejects_different_case_sets(history):
    base = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a", "b"),
    )
    candidate = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a", "c"),
    )
    with pytest.raises(ValueError, match="different case sets"):
        history.compare(base, candidate)


def test_compare_latest_detects_regressions_over_history(history):
    history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1,
        results=_results("a", "b"),
    )
    history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1,
        results=_results("a", "b", failed=("a",)),
    )
    comparison = history.compare_latest("main")
    assert comparison is not None
    assert comparison.regressions == ("a",)
    assert comparison.has_regressions
    # Fewer than two runs -> no comparison possible.
    history.record_run(
        model_id="alt", model_version="alt-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a"),
    )
    assert history.compare_latest("alt") is None
    assert history.compare_latest("never-ran") is None


def test_compare_latest_all_green_is_not_a_regression(history):
    history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1,
        results=_results("a", "b", failed=("b",)),
    )
    history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=_results("a", "b"),
    )
    comparison = history.compare_latest("main")
    assert comparison is not None
    assert not comparison.has_regressions
    assert comparison.fixes == ("b",)


# -------------------------------------------------------- deterministic
def test_deterministic_replay_records_identical_results(history):
    results = _results("a", "b", failed=("b",))
    first = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=results,
    )
    second = history.record_run(
        model_id="main", model_version="main-model",
        prompt_id="assistant.default", prompt_version=1, results=results,
    )
    assert first.results == second.results
    assert (first.passed, first.total) == (second.passed, second.total)
    # Only identity and timestamp differ.
    assert first.run_id != second.run_id


# ------------------------------------------------------- runner recording
@pytest.fixture()
def repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _fake_llm_chain(repo, answer_text: str) -> FallbackAssistantProvider:
    """The REAL provider chain with a deterministic fake LLM transport
    (the accepted eval harness shape: primary transport + rules fallback)."""
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": answer_text}}]}
            )
        )
    )
    primary = LlmAssistantProvider(
        client, model="eval-model", base_url="http://eval.example",
        retry_attempts=1, retry_backoff_seconds=0,
    )
    fallback = RuleBasedAssistantProvider(
        repo, permission_evaluator=ObjectPermissionEvaluator()
    )
    return FallbackAssistantProvider(primary, fallback)


def _eval_use_case(db, repo, vectors, provider) -> AskQuestionUseCase:
    """The REAL ask pipeline (retrieval, context, prompt, provider,
    citations, verification, persistence) — the accepted eval harness."""
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


def _seed_world(db, repo) -> FakeVectorRepository:
    """One document + the eval asker, both indexed (the eval harness world:
    the asker must be a real, readable user for the pipeline to retrieve)."""
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "Quantum Mechanics Notes", created_by="f:1"
    )
    asker = UniversalObject.create(
        ObjectType.USER, "eval", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:eval-0001"),
    )
    asker.pop_domain_events()
    repo.save(asker)
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    doc_events = doc.pop_domain_events()
    repo.save(doc, outbox_events=[to_outbox_row(e) for e in doc_events])
    SearchIndexApplier(db).apply_pending()
    snap = SnapshotMapper.to_snapshot(doc)
    search_doc = to_search_document(snap)
    vectors.upsert(
        VectorDocument(
            object_id=search_doc.object_id,
            object_type=search_doc.object_type,
            title=search_doc.title,
            metadata_text=search_doc.metadata_text,
            version=search_doc.version,
            vector=tuple(embedder.embed(search_text(snap))),
        )
    )
    return vectors


def _registry() -> ModelRegistry:
    registry = ModelRegistry(default_id="main")
    registry.register(ModelSpec(id="main", base_url="http://a/v1", model="main-model"))
    registry.register(
        ModelSpec(id="rules", model="rules-v1", provider_kind=PROVIDER_KIND_RULES)
    )
    return registry


def _prompt_registry() -> PromptRegistry:
    prompt_registry = PromptRegistry()
    prompt_registry.register(
        PromptAsset(
            id=DEFAULT_PROMPT_ID, version=1, version_label="1.0",
            owner="assistant", system_text="You are AcademicOS Assistant.",
        )
    )
    return prompt_registry


def _runner_world(db, repo):
    vectors = _seed_world(db, repo)

    def build_use_case(model_id: str):
        answer = "marker answer" if model_id == "main" else "unrelated text"
        return _eval_use_case(db, repo, vectors, _fake_llm_chain(repo, answer))

    return build_use_case


def test_runner_records_every_model_run(db, repo, history):
    registry = _registry()
    cases = [EvalCase(name="marker", question="find quantum",
                      expected_contains=("marker",))]

    outcomes = run_eval_suite_across_models(
        registry, repo, _runner_world(db, repo), cases,
        history=history, prompt_registry=_prompt_registry(),
    )

    # Both models were evaluated AND recorded.
    assert set(outcomes) == {"main", "rules"}
    main_run = history.latest("main")
    assert main_run is not None
    assert main_run.model_id == "main"
    assert main_run.model_version == "main-model"  # deployed model name stored
    assert main_run.prompt_id == DEFAULT_PROMPT_ID
    assert main_run.prompt_version == 1  # resolved from the registry
    assert main_run.passed == 1 and main_run.total == 1

    # A failing model's run is recorded too, with its failure details.
    rules_run = history.latest("rules")
    assert rules_run is not None
    assert rules_run.passed == 0 and rules_run.total == 1
    assert rules_run.results[0].passed is False
    assert rules_run.results[0].details


def test_runner_records_prompt_version_from_registry_at_run_time(db, repo, history):
    registry = _registry()
    cases = [EvalCase(name="marker", question="find quantum",
                      expected_contains=("marker",))]
    prompt_registry = _prompt_registry()
    build_use_case = _runner_world(db, repo)

    run_eval_suite_across_models(
        registry, repo, build_use_case, cases,
        history=history, prompt_registry=prompt_registry,
    )
    assert history.latest("main").prompt_version == 1

    # A newer prompt version is registered: the next run records it.
    prompt_registry.register(
        PromptAsset(
            id=DEFAULT_PROMPT_ID, version=2, version_label="2.0",
            owner="assistant", system_text="You are AcademicOS Assistant. v2",
        )
    )
    run_eval_suite_across_models(
        registry, repo, build_use_case, cases,
        history=history, prompt_registry=prompt_registry,
    )
    assert history.latest("main").prompt_version == 2
    assert [r.prompt_version for r in history.recent("main", 10)] == [2, 1]


def test_runner_requires_prompt_registry_when_recording(db, repo, history):
    with pytest.raises(ValueError, match="prompt_registry"):
        run_eval_suite_across_models(
            _registry(), repo, _runner_world(db, repo),
            [EvalCase(name="c", question="q")], history=history,
        )


def test_partial_failure_records_completed_models(db, repo, history):
    registry = ModelRegistry(default_id="alpha")
    registry.register(ModelSpec(id="alpha", base_url="http://a/v1", model="alpha-model"))
    registry.register(ModelSpec(id="omega", base_url="http://o/v1", model="omega-model"))
    cases = [EvalCase(name="marker", question="find quantum",
                      expected_contains=("marker",))]
    vectors = _seed_world(db, repo)

    def build_use_case(model_id: str):
        if model_id == "omega":
            raise RuntimeError("provider exploded")
        return _eval_use_case(
            db, repo, vectors, _fake_llm_chain(repo, "marker answer")
        )

    with pytest.raises(RuntimeError, match="exploded"):
        run_eval_suite_across_models(
            registry, repo, build_use_case, cases,
            history=history, prompt_registry=_prompt_registry(),
        )

    # The completed model's run is durable; the crashed model has none.
    assert history.latest("alpha") is not None
    assert history.latest("alpha").passed == 1
    assert history.latest("omega") is None


def test_runner_backward_compatible_without_history(db, repo):
    registry = _registry()
    cases = [EvalCase(name="marker", question="find quantum",
                      expected_contains=("marker",))]

    # Pre-M3 call shape: no history, no prompt registry — same outcomes.
    outcomes = run_eval_suite_across_models(
        registry, repo, _runner_world(db, repo), cases
    )
    assert set(outcomes) == {"main", "rules"}
    assert outcomes["main"][1] == 1

    # Nothing was recorded.
    store = SQLEvalRunStore(db)
    assert store.recent_by_model("main", 10) == []
    assert store.recent_by_model("rules", 10) == []
