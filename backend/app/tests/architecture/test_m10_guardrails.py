"""V3 M10 architecture guardrails (ADR-057).

Pins the durable-jobs contracts:

- the queue is ONE generic jobs table (no per-type subsystem, no new queue);
- claim is at-least-once with a lease (SKIP LOCKED on PG, atomic lease on
  SQLite) — never a second queue/event bus;
- worker.py / relay.py are separate processes; the API only submits;
- the in-process IntakeJobManager is retained (rollback path);
- no Kafka/Redis/Celery/Temporal anywhere in the job path.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_one_generic_jobs_table() -> None:
    # A single generic jobs table + one attempt table (never per-type tables,
    # never a second queue/event-bus).
    model_src = (
        REPO / "backend" / "app" / "infrastructure" / "db" / "models" / "job_model.py"
    ).read_text(encoding="utf-8")
    assert "class JobModel" in model_src
    assert "class JobAttemptModel" in model_src

    import app.infrastructure.persistence.job_store as mod

    src = inspect.getsource(mod)
    for forbidden in ("kafka", "celery", "redis", "temporal", "sqs", "rabbit"):
        assert forbidden not in src.lower()


def test_claim_uses_skip_locked_on_postgres() -> None:
    import app.infrastructure.persistence.job_store as mod

    src = inspect.getsource(mod)
    assert "SKIP LOCKED" in src


def test_worker_and_relay_are_separate_processes() -> None:
    worker = (REPO / "backend" / "scripts" / "worker.py").read_text(encoding="utf-8")
    relay = (REPO / "backend" / "scripts" / "relay.py").read_text(encoding="utf-8")
    assert "claim_next" in worker
    assert "apply_pending" in relay


def test_in_process_backend_retained() -> None:
    # IntakeJobManager (the in-process backend) is untouched by M10.
    src = (REPO / "backend" / "app" / "application" / "intake" / "jobs.py").read_text(
        encoding="utf-8"
    )
    assert "class IntakeJobManager" in src


def test_backpressure_is_bounded() -> None:
    import app.application.services.backpressure as mod

    src = inspect.getsource(mod)
    assert "global_limit" in src and "per_user_limit" in src and "per_type_limit" in src
