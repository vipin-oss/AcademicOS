"""V3 M10 backpressure limiter unit tests (ADR-057)."""

from __future__ import annotations

from app.application.services.backpressure import BackpressureLimiter


def test_global_limit_blocks():
    limiter = BackpressureLimiter(global_limit=1, per_user_limit=5, per_type_limit=5)
    assert limiter.allow(job_id="a", job_type="t", owner_user_id="u1")
    limiter.start(job_id="a", job_type="t", owner_user_id="u1")
    assert not limiter.allow(job_id="b", job_type="t", owner_user_id="u2")
    limiter.finish(job_id="a", job_type="t", owner_user_id="u1")
    assert limiter.allow(job_id="b", job_type="t", owner_user_id="u2")


def test_per_user_quota_blocks():
    limiter = BackpressureLimiter(global_limit=10, per_user_limit=1, per_type_limit=10)
    limiter.start(job_id="a", job_type="t", owner_user_id="u1")
    assert not limiter.allow(job_id="b", job_type="t", owner_user_id="u1")
    assert limiter.allow(job_id="c", job_type="t", owner_user_id="u2")


def test_per_type_concurrency_blocks():
    limiter = BackpressureLimiter(global_limit=10, per_user_limit=10, per_type_limit=1)
    limiter.start(job_id="a", job_type="extraction", owner_user_id="u1")
    assert not limiter.allow(job_id="b", job_type="extraction", owner_user_id="u2")
    assert limiter.allow(job_id="c", job_type="export", owner_user_id="u2")


def test_finish_decrements():
    limiter = BackpressureLimiter(global_limit=10, per_user_limit=2, per_type_limit=2)
    limiter.start(job_id="a", job_type="t", owner_user_id="u1")
    limiter.start(job_id="b", job_type="t", owner_user_id="u1")
    assert limiter.running() == 2
    limiter.finish(job_id="a", job_type="t", owner_user_id="u1")
    assert limiter.running() == 1
    assert limiter.allow(job_id="c", job_type="t", owner_user_id="u1")
