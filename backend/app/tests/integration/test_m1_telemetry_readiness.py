"""V3 M1 gate — instrumentation, readiness and pre-warm.

M1's promise is *truthful measurement*: every later milestone's latency claim
is verified against a baseline, so the instrumentation itself must be proven
present, correct and harmless.

These tests pin:
- every response carries request/trace identity and a measured duration;
- inbound correlation ids are honoured, and hostile ones rejected;
- readiness reports each subsystem honestly and never raises;
- pre-warm never fabricates residency and never breaks startup.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.middleware.telemetry import (
    HEADER_REQUEST_ID,
    HEADER_RESPONSE_TIME,
    HEADER_TRACE_ID,
    RequestTelemetry,
)
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """TestClient with the repo's standard SQLite session override.

    Readiness probes hit the database, so the suite supplies one the same way
    every other integration test does — the tests must not depend on ambient
    infrastructure being up.
    """
    app = create_app()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session.close()


# ----------------------------------------------------------------- telemetry
def test_every_response_carries_identity_and_duration(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers[HEADER_REQUEST_ID]
    assert response.headers[HEADER_TRACE_ID]
    # total_ms is measured, not fabricated
    assert float(response.headers[HEADER_RESPONSE_TIME]) >= 0.0


def test_request_id_is_unique_per_request(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers[HEADER_REQUEST_ID]
    second = client.get("/api/v1/health").headers[HEADER_REQUEST_ID]
    assert first != second


def test_inbound_correlation_ids_are_honoured(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health",
        headers={HEADER_REQUEST_ID: "abc-123", HEADER_TRACE_ID: "trace-xyz"},
    )
    assert response.headers[HEADER_REQUEST_ID] == "abc-123"
    assert response.headers[HEADER_TRACE_ID] == "trace-xyz"


def test_trace_id_defaults_to_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={HEADER_REQUEST_ID: "solo-1"})
    assert response.headers[HEADER_TRACE_ID] == "solo-1"


def test_hostile_inbound_id_is_rejected_not_echoed(client: TestClient) -> None:
    """Header-injection guard: unsafe ids are replaced, never reflected."""
    response = client.get(
        "/api/v1/health", headers={HEADER_REQUEST_ID: "bad id\r\nX-Evil: 1"}
    )
    echoed = response.headers[HEADER_REQUEST_ID]
    assert echoed != "bad id\r\nX-Evil: 1"
    assert "\r" not in echoed and "\n" not in echoed and " " not in echoed


def test_telemetry_accessor_is_null_safe() -> None:
    """Unit-tested code paths have no request; the accessor must not raise."""
    assert RequestTelemetry.of(None) is None


def test_telemetry_records_stages_and_facts() -> None:
    telemetry = RequestTelemetry(request_id="r1", trace_id="t1")
    telemetry.record("vector_retrieval_ms", 12.5)
    telemetry.record("vector_retrieval_ms", 2.5)  # accumulates
    telemetry.record("ignored_ms", -1.0)  # negatives ignored
    telemetry.fact("rung", 0)

    snapshot = telemetry.snapshot()
    assert snapshot["vector_retrieval_ms"] == 15.0
    assert "ignored_ms" not in snapshot
    assert snapshot["rung"] == 0
    assert snapshot["request_id"] == "r1"
    assert snapshot["total_ms"] >= 0.0


# ----------------------------------------------------------------- readiness
def test_liveness_contract_unchanged(client: TestClient) -> None:
    """R1's /health contract must not regress — scripts depend on it."""
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "academicos-api"
    assert "version" in body and "environment" in body


def test_readiness_reports_every_subsystem(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    # 200 when serving is possible, 503 only on a hard dependency failure.
    assert response.status_code in (200, 503)
    checks = response.json()["checks"]
    for subsystem in ("database", "outbox", "vector", "ai"):
        assert subsystem in checks, f"missing readiness probe: {subsystem}"
        assert "status" in checks[subsystem]


def test_readiness_reports_alembic_revision(client: TestClient) -> None:
    """Schema-vs-code drift is a first-class M1 fact."""
    database = client.get("/api/v1/health/ready").json()["checks"]["database"]
    assert "alembic_revision" in database


def test_readiness_reports_model_residency(client: TestClient) -> None:
    """``model_resident`` is the M1 speed fact (audit finding A4)."""
    ai = client.get("/api/v1/health/ready").json()["checks"]["ai"]
    assert "model_resident" in ai
    assert isinstance(ai["model_resident"], bool)


def test_readiness_never_raises_when_vector_is_down() -> None:
    """Qdrant down is DEGRADED with a lexical fallback, never fatal."""
    from app.infrastructure.db.readiness import STATUS_DEGRADED, vector_probe

    def broken_factory():
        raise ConnectionError("qdrant unreachable")

    probe = vector_probe(client_factory=broken_factory)
    assert probe.status == STATUS_DEGRADED
    assert probe.facts["fallback"] == "lexical"


def test_aggregate_status_is_worst_of() -> None:
    from app.infrastructure.db.readiness import (
        STATUS_DEGRADED,
        STATUS_ERROR,
        STATUS_OK,
        ProbeResult,
        aggregate_status,
    )

    ok = ProbeResult(name="a", status=STATUS_OK)
    degraded = ProbeResult(name="b", status=STATUS_DEGRADED)
    error = ProbeResult(name="c", status=STATUS_ERROR)

    assert aggregate_status([ok, ok]) == STATUS_OK
    assert aggregate_status([ok, degraded]) == STATUS_DEGRADED
    assert aggregate_status([ok, degraded, error]) == STATUS_ERROR


# ------------------------------------------------------------------- prewarm
def test_prewarm_without_provider_does_not_claim_residency() -> None:
    """Honest zeros: no provider means not resident, and no exception."""
    from app.application.ai.warmup import prewarm, reset_warmup_state

    class _NoProviders:
        provider_ids: tuple = ()

    reset_warmup_state()
    state = prewarm(_NoProviders())
    assert state.attempted is True
    assert state.resident is False
    assert "no provider" in state.detail
    reset_warmup_state()


def test_prewarm_survives_gateway_failure() -> None:
    """A broken provider degrades health; it must never break startup."""
    from app.application.ai.warmup import prewarm, reset_warmup_state

    class _Boom:
        provider_ids = ("x",)

        def gateway(self, provider_id=None):
            raise RuntimeError("provider exploded")

    reset_warmup_state()
    state = prewarm(_Boom())
    assert state.resident is False
    assert "RuntimeError" in state.detail
    reset_warmup_state()


def test_prewarm_marks_resident_on_success() -> None:
    from app.application.ai.warmup import prewarm, reset_warmup_state, warmup_state

    class _Health:
        executable = True

    class _Result:
        model = "test-model"

    class _Gateway:
        def health(self):
            return _Health()

        def generate(self, prompt):
            assert prompt.max_tokens == 1  # minimal prompt, not a real workload
            return _Result()

    class _Core:
        provider_ids = ("local",)

        def gateway(self, provider_id=None):
            return _Gateway()

    reset_warmup_state()
    state = prewarm(_Core())
    assert state.resident is True
    assert state.model == "test-model"
    assert state.warmup_ms is not None
    assert warmup_state().resident is True  # state is observable by /health
    reset_warmup_state()


def test_prewarm_does_not_claim_residency_for_unexecutable_provider() -> None:
    from app.application.ai.warmup import prewarm, reset_warmup_state

    class _Health:
        executable = False

    class _Gateway:
        def health(self):
            return _Health()

    class _Core:
        provider_ids = ("placeholder",)

        def gateway(self, provider_id=None):
            return _Gateway()

    reset_warmup_state()
    state = prewarm(_Core())
    assert state.resident is False
    assert "not executable" in state.detail
    reset_warmup_state()
