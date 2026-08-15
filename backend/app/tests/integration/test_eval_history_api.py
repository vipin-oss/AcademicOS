"""Integration tests for the evaluation history API (Sprint-7 M4).

Full TestClient surface over the durable eval_runs records: run listing
(all / filtered / bounded), single-run fetch with the complete per-case
shape, comparison of any two runs (regression/fix/stable summaries),
per-model latest-two regression detection, the 404/422 error mappings,
and the authentication gate.

Mirrors ``test_assistant_api.py`` / ``test_search_api.py``: StaticPool
in-memory SQLite, the app imported via ``pytest.importorskip``, the
``get_db`` / ``get_current_user`` dependencies overridden, seeding done
through the REAL ``EvaluationHistory`` service (the same wiring the
endpoints use).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.dependencies.auth import get_current_user  # noqa: E402
from app.application.services.assistant_eval import (  # noqa: E402
    EvalResult,
    EvaluationHistory,
)
from app.domain.entities.object import UniversalObject  # noqa: E402
from app.domain.value_objects.enums import ObjectStatus, ObjectType  # noqa: E402
from app.domain.value_objects.object_id import ObjectId  # noqa: E402
from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.infrastructure.persistence.eval_run_store import SQLEvalRunStore  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1/assistant/eval"


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
    history = EvaluationHistory(SQLEvalRunStore(session))
    with TestClient(app) as client:
        yield client, history
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(history: EvaluationHistory) -> dict:
    """Two runs of ``main`` (prompt v1 -> v2, one case regressing and one
    fixing), two clean runs of ``alt``, and one run of ``solo`` — the
    deterministic comparison fixture."""
    base = history.record_run(
        model_id="main",
        model_version="main-model",
        prompt_id="assistant.default",
        prompt_version=1,
        results=(
            EvalResult(name="a", passed=True),
            EvalResult(name="b", passed=True),
            EvalResult(name="c", passed=False, details=("missing marker",)),
        ),
    )
    candidate = history.record_run(
        model_id="main",
        model_version="main-model",
        prompt_id="assistant.default",
        prompt_version=2,
        results=(
            EvalResult(name="a", passed=False, details=("missing marker",)),
            EvalResult(name="b", passed=True),
            EvalResult(name="c", passed=True),
        ),
    )
    alt1 = history.record_run(
        model_id="alt",
        model_version="alt-model",
        prompt_id="assistant.default",
        prompt_version=1,
        results=(EvalResult(name="a", passed=True),),
    )
    alt2 = history.record_run(
        model_id="alt",
        model_version="alt-model",
        prompt_id="assistant.default",
        prompt_version=2,
        results=(EvalResult(name="a", passed=True),),
    )
    solo = history.record_run(
        model_id="solo",
        model_version="solo-model",
        prompt_id="assistant.default",
        prompt_version=1,
        results=(EvalResult(name="a", passed=True),),
    )
    return {"base": base, "candidate": candidate, "alt1": alt1, "alt2": alt2, "solo": solo}


# -------------------------------------------------------------------- auth
def test_eval_endpoints_require_authentication(harness):
    client, _ = harness
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get(f"{API}/runs").status_code == 401
    assert client.get(f"{API}/runs/some-run").status_code == 401
    assert client.post(f"{API}/compare", json={"base_run_id": "x", "candidate_run_id": "y"}).status_code == 401
    assert client.get(f"{API}/models/main/compare/latest").status_code == 401


# ------------------------------------------------------------------- list
def test_list_runs_empty_bootstrap(harness):
    client, _ = harness
    r = client.get(f"{API}/runs")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_list_runs_all_newest_first_with_full_shape(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/runs")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["run_id"] for i in items] == [
        seeded["solo"].run_id,
        seeded["alt2"].run_id,
        seeded["alt1"].run_id,
        seeded["candidate"].run_id,
        seeded["base"].run_id,
    ]
    run = items[0]
    assert run["model_id"] == "solo"
    assert run["model_version"] == "solo-model"
    assert run["prompt_id"] == "assistant.default"
    assert run["prompt_version"] == 1
    assert run["passed"] == 1 and run["total"] == 1
    assert run["created_at"]
    # Per-case benchmark results with failure details.
    main_run = next(i for i in items if i["run_id"] == seeded["base"].run_id)
    assert main_run["passed"] == 2 and main_run["total"] == 3
    assert main_run["results"][2] == {
        "name": "c",
        "passed": False,
        "details": ["missing marker"],
    }


def test_list_runs_filter_by_model(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/runs", params={"model_id": "main"})
    assert [i["run_id"] for i in r.json()["items"]] == [
        seeded["candidate"].run_id,
        seeded["base"].run_id,
    ]
    r = client.get(f"{API}/runs", params={"model_id": "alt"})
    assert [i["run_id"] for i in r.json()["items"]] == [
        seeded["alt2"].run_id,
        seeded["alt1"].run_id,
    ]
    r = client.get(f"{API}/runs", params={"model_id": "never-ran"})
    assert r.json()["items"] == []


def test_list_runs_respects_limit_bounds(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/runs", params={"limit": 1})
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["run_id"] == seeded["solo"].run_id
    assert client.get(f"{API}/runs", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/runs", params={"limit": 101}).status_code == 422


# ------------------------------------------------------------ single run
def test_get_run_returns_the_recorded_run(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/runs/{seeded['candidate'].run_id}")
    assert r.status_code == 200
    run = r.json()
    assert run["run_id"] == seeded["candidate"].run_id
    assert run["model_version"] == "main-model"
    assert run["prompt_version"] == 2
    assert run["passed"] == 2 and run["total"] == 3
    assert run["results"][0] == {
        "name": "a",
        "passed": False,
        "details": ["missing marker"],
    }


def test_get_unknown_run_returns_404(harness):
    client, _ = harness
    r = client.get(f"{API}/runs/never-recorded")
    assert r.status_code == 404
    assert "Unknown evaluation run" in r.json()["detail"]


# ------------------------------------------------------------- compare
def test_compare_any_two_runs(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.post(
        f"{API}/compare",
        json={
            "base_run_id": seeded["base"].run_id,
            "candidate_run_id": seeded["candidate"].run_id,
        },
    )
    assert r.status_code == 200
    comparison = r.json()
    assert comparison["base_run_id"] == seeded["base"].run_id
    assert comparison["candidate_run_id"] == seeded["candidate"].run_id
    assert comparison["regressions"] == ["a"]
    assert comparison["fixes"] == ["c"]
    assert comparison["stable_passes"] == ["b"]
    assert comparison["stable_failures"] == []
    assert comparison["has_regressions"] is True
    assert comparison["base_passed"] == 2
    assert comparison["candidate_passed"] == 2
    assert comparison["total"] == 3


def test_compare_unknown_run_returns_404(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.post(
        f"{API}/compare",
        json={"base_run_id": seeded["base"].run_id, "candidate_run_id": "missing"},
    )
    assert r.status_code == 404
    r = client.post(
        f"{API}/compare",
        json={"base_run_id": "missing", "candidate_run_id": seeded["base"].run_id},
    )
    assert r.status_code == 404


def test_compare_rejects_different_case_sets(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.post(
        f"{API}/compare",
        json={
            "base_run_id": seeded["base"].run_id,
            "candidate_run_id": seeded["alt1"].run_id,
        },
    )
    assert r.status_code == 422
    assert "different case sets" in r.json()["detail"]


# ------------------------------------------------- latest-two comparison
def test_compare_latest_two_runs_for_a_model(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/models/main/compare/latest")
    assert r.status_code == 200
    comparison = r.json()
    assert comparison["base_run_id"] == seeded["base"].run_id
    assert comparison["candidate_run_id"] == seeded["candidate"].run_id
    assert comparison["regressions"] == ["a"]
    assert comparison["fixes"] == ["c"]
    assert comparison["has_regressions"] is True


def test_compare_latest_no_regressions_is_a_clean_report(harness):
    client, history = harness
    seeded = _seed(history)
    r = client.get(f"{API}/models/alt/compare/latest")
    assert r.status_code == 200
    comparison = r.json()
    assert comparison["regressions"] == []
    assert comparison["fixes"] == []
    assert comparison["stable_passes"] == ["a"]
    assert comparison["has_regressions"] is False
    assert comparison["base_run_id"] == seeded["alt1"].run_id
    assert comparison["candidate_run_id"] == seeded["alt2"].run_id


def test_compare_latest_requires_two_runs(harness):
    client, history = harness
    _seed(history)
    # ``solo`` has exactly one recorded run -> no comparison; unknown model -> none.
    assert client.get(f"{API}/models/solo/compare/latest").status_code == 404
    assert client.get(f"{API}/models/never-ran/compare/latest").status_code == 404
