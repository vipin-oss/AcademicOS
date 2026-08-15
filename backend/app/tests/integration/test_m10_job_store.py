"""V3 M10 durable job queue tests (ADR-057): claim, complete, fail, reap, scheduler."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.value_objects.job import Job, JobStatus
from app.infrastructure.db.models.job_model import JobAttemptModel, JobModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.job_store import SQLJobStore

NOW = "2026-08-15T00:00:00+00:00"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _job(job_id, *, job_type="extraction", priority=0, next_run_at=None, cron=None, max_attempts=3):
    return Job(
        id=job_id, job_type=job_type, payload={"x": 1}, priority=priority,
        created_at=NOW, next_run_at=next_run_at, cron_expr=cron, max_attempts=max_attempts,
    )


def test_submit_is_idempotent(db):
    store = SQLJobStore(db)
    store.submit(_job("j1"))
    db.commit()
    store.submit(_job("j1"))
    db.commit()
    # only one row
    from sqlalchemy import text

    count = db.execute(text("SELECT COUNT(*) FROM jobs WHERE id='j1'")).scalar()
    assert count == 1


def test_claim_next_is_exactly_one_and_priority_ordered(db):
    store = SQLJobStore(db)
    store.submit(_job("low", priority=0))
    store.submit(_job("high", priority=10))
    db.commit()

    first = store.claim_next("w1", now=NOW)
    assert first is not None and first.id == "high"
    assert first.status == JobStatus.RUNNING.value

    second = store.claim_next("w2", now=NOW)
    assert second is not None and second.id == "low"

    # both leased -> no third claim
    assert store.claim_next("w3", now=NOW) is None


def test_complete_marks_succeeded_and_records_attempt(db):
    store = SQLJobStore(db)
    store.submit(_job("j1"))
    db.commit()
    store.claim_next("w1", now=NOW)
    store.complete("j1", worker_id="w1", now=NOW)

    from sqlalchemy import text

    status = db.execute(text("SELECT status FROM jobs WHERE id='j1'")).scalar()
    assert status == "succeeded"
    # one attempt per claim, finalized in place to 'succeeded'
    attempts = db.execute(text("SELECT status FROM job_attempts WHERE job_id='j1'")).scalars().all()
    assert attempts == ["succeeded"]


def test_fail_retries_then_exhausts(db):
    store = SQLJobStore(db)
    store.submit(_job("j1", max_attempts=2))
    db.commit()

    store.claim_next("w1", now=NOW)
    store.fail("j1", worker_id="w1", now=NOW, error="boom")
    # attempts=1 < 2 -> retryable
    from sqlalchemy import text

    assert db.execute(text("SELECT status FROM jobs WHERE id='j1'")).scalar() == "retryable"

    store.claim_next("w1", now=NOW)
    store.fail("j1", worker_id="w1", now=NOW, error="boom")
    # attempts=2 >= 2 -> failed (exhausted)
    assert db.execute(text("SELECT status FROM jobs WHERE id='j1'")).scalar() == "failed"


def test_reap_stale_releases_crashed_worker_lease(db):
    store = SQLJobStore(db)
    store.submit(_job("j1"))
    db.commit()
    store.claim_next("w1", now=NOW)  # leases until NOW+60

    # a future "now" past the lease -> reap releases it
    future = "2026-08-15T00:02:00+00:00"
    released = store.reap_stale(now=future)
    assert released == 1
    # now claimable again
    assert store.claim_next("w2", now=future) is not None


def test_scheduler_due_returns_cron_jobs(db):
    store = SQLJobStore(db)
    store.submit(_job("sched", job_type="scheduled", next_run_at="2026-08-14T00:00:00+00:00", cron="0 * * * *"))
    store.submit(_job("future", job_type="scheduled", next_run_at="2026-09-01T00:00:00+00:00", cron="0 * * * *"))
    db.commit()

    due = store.scheduler_due(now=NOW)
    assert [j.id for j in due] == ["sched"]
