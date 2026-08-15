"""Application port: durable job queue (V3 M10, ADR-057).

The seam between the API (which submits jobs) and the worker process (which
claims and executes them). At-least-once with idempotent handlers: a job is
claimed by exactly one worker via a lease (``FOR UPDATE SKIP LOCKED`` on
PostgreSQL; an atomic conditional lease on SQLite), and a crashed worker's
lease is reaped so the job is re-claimed.
"""

from __future__ import annotations

import abc

from app.domain.value_objects.job import Job


class JobStore(abc.ABC):
    @abc.abstractmethod
    def submit(self, job: Job) -> Job:
        """Enqueue a job (idempotent by job id)."""

    @abc.abstractmethod
    def claim_next(
        self,
        worker_id: str,
        *,
        job_types: tuple[str, ...] | None = None,
        now: str,
        lease_seconds: int = 60,
    ) -> Job | None:
        """Atomically claim the highest-priority due job (or None)."""

    @abc.abstractmethod
    def complete(self, job_id: str, *, worker_id: str, now: str) -> None:
        """Mark a job SUCCEEDED and record its attempt."""

    @abc.abstractmethod
    def fail(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: str,
        error: str,
    ) -> None:
        """Record a failed attempt; mark the job RETRYABLE (within max_attempts)
        or FAILED (exhausted)."""

    @abc.abstractmethod
    def reap_stale(self, *, now: str) -> int:
        """Release leases whose ``locked_until`` passed (crashed workers)."""

    @abc.abstractmethod
    def scheduler_due(self, *, now: str) -> list[Job]:
        """Recurring (cron) jobs whose next_run_at has passed and which need a
        fresh run enqueued."""
