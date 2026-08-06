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

from app.application.services.assistant_eval import (
    EvaluationHistory,
    EvalResult,
    EvalRun,
)
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.eval_run_store import SQLEvalRunStore


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
