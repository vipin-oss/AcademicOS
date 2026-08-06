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
