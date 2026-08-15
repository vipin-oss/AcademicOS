"""SQL implementation of the durable job queue (V3 M10, ADR-057).

Dialect-aware claim:

- PostgreSQL: ``SELECT … FOR UPDATE SKIP LOCKED`` — exactly-one claimant.
- SQLite: an atomic conditional UPDATE lease (single-writer, so a WHERE-guarded
  UPDATE that flips ``locked_until``/``status`` from a claimable state is the
  safe equivalent of SKIP LOCKED).

At-least-once with idempotent handlers: a crashed worker's lease is reaped by
``reap_stale`` and the job is re-claimed; ``attempts``/``max_attempts`` bound
retries; every completion/failure writes a ``job_attempts`` audit row.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.application.ports.job_store import JobStore
from app.domain.value_objects.job import Job, JobStatus
from app.infrastructure.db.models.job_model import JobModel

_CLAIMABLE = (JobStatus.PENDING.value, JobStatus.RETRYABLE.value)


def _utcnow_iso_placeholder() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).isoformat()


def _lease_until(now: str, lease_seconds: int) -> str:
    import datetime as dt

    base = dt.datetime.fromisoformat(now)
    return (base + dt.timedelta(seconds=lease_seconds)).isoformat()


class SQLJobStore(JobStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(self, job: Job) -> Job:
        existing = self._session.execute(
            select(JobModel).where(JobModel.id == job.id)
        ).scalars().first()
        if existing is not None:
            return job  # idempotent
        self._session.add(
            JobModel(
                id=job.id,
                job_type=job.job_type,
                payload=json.dumps(job.payload),
                status=job.status,
                priority=job.priority,
                tenant_id=job.tenant_id,
                owner_user_id=job.owner_user_id,
                created_at=job.created_at or _utcnow_iso_placeholder(),
                next_run_at=job.next_run_at,
                cron_expr=job.cron_expr,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                locked_until=job.locked_until,
            )
        )
        return job

    def claim_next(
        self,
        worker_id: str,
        *,
        job_types: tuple[str, ...] | None = None,
        now: str,
        lease_seconds: int = 60,
    ) -> Job | None:
        lease = _lease_until(now, lease_seconds)
        params: dict = {"now": now}
        if job_types:
            params["types"] = tuple(job_types)
        if self._session.get_bind().dialect.name == "postgresql":
            where = (
                "status IN ('pending','retryable') "
                "AND (next_run_at IS NULL OR next_run_at <= :now) "
                "AND (locked_until IS NULL OR locked_until <= :now)"
            )
            if job_types:
                where += " AND job_type IN :types"
            stmt = text(
                f"SELECT id FROM jobs WHERE {where} "
                "ORDER BY priority DESC, created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
            )
            row = self._session.execute(stmt, params).first()
            if row is None:
                return None
            job_id = row[0]
        else:
            # SQLite: atomic conditional lease (single-writer).
            where = (
                "status IN ('pending','retryable') "
                "AND (next_run_at IS NULL OR next_run_at <= :now) "
                "AND (locked_until IS NULL OR locked_until <= :now)"
            )
            if job_types:
                where += " AND job_type IN :types"
            row = self._session.execute(
                text(
                    f"SELECT id FROM jobs WHERE {where} "
                    "ORDER BY priority DESC, created_at ASC LIMIT 1"
                ),
                params,
            ).first()
            if row is None:
                return None
            job_id = row[0]
            result = self._session.execute(
                text(
                    "UPDATE jobs SET locked_until = :lease, status = 'running' "
                    "WHERE id = :id AND (locked_until IS NULL OR locked_until <= :now) "
                    "AND status IN ('pending','retryable')"
                ),
                {"lease": lease, "id": job_id, "now": now},
            )
            if result.rowcount == 0:
                return None  # lost the race to another worker

        # Common: lock the row (mark running + lease + attempt increment).
        self._session.execute(
            text(
                "UPDATE jobs SET locked_until = :lease, status = 'running', "
                "attempts = attempts + 1 WHERE id = :id"
            ),
            {"lease": lease, "id": job_id},
        )
        self._session.execute(
            text(
                "INSERT INTO job_attempts (id, job_id, worker_id, status, started_at, "
                "tenant_id, owner_user_id) VALUES (:id, :job, :worker, 'running', :now, "
                "'default', 'default')"
            ),
            {
                "id": uuid.uuid4().hex,
                "job": job_id,
                "worker": worker_id,
                "now": now,
            },
        )
        self._session.commit()
        model = self._session.execute(
            select(JobModel).where(JobModel.id == job_id)
        ).scalars().first()
        return _to_job(model)

    def complete(self, job_id: str, *, worker_id: str, now: str) -> None:
        self._session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(status=JobStatus.SUCCEEDED.value, locked_until=None)
        )
        self._finalize_attempt(job_id, worker_id, "succeeded", None, now)
        self._session.commit()

    def fail(self, job_id: str, *, worker_id: str, now: str, error: str) -> None:
        model = self._session.execute(
            select(JobModel).where(JobModel.id == job_id)
        ).scalars().first()
        if model is None:
            return
        exhausted = model.attempts >= model.max_attempts
        new_status = JobStatus.FAILED.value if exhausted else JobStatus.RETRYABLE.value
        self._session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(status=new_status, locked_until=None)
        )
        self._finalize_attempt(job_id, worker_id, "failed", error, now)
        self._session.commit()

    def reap_stale(self, *, now: str) -> int:
        result = self._session.execute(
            text(
                "UPDATE jobs SET status = 'retryable', locked_until = NULL "
                "WHERE status = 'running' AND locked_until IS NOT NULL AND locked_until <= :now"
            ),
            {"now": now},
        )
        self._session.commit()
        return result.rowcount or 0

    def scheduler_due(self, *, now: str) -> list[Job]:
        rows = self._session.execute(
            select(JobModel).where(
                JobModel.cron_expr.is_not(None),
                JobModel.next_run_at.is_not(None),
                JobModel.next_run_at <= now,
            )
        ).scalars().all()
        return [_to_job(r) for r in rows]

    def _finalize_attempt(self, job_id, worker_id, status, error, now) -> None:
        # finalize the most recent running attempt for this worker/job
        self._session.execute(
            text(
                "UPDATE job_attempts SET status = :status, error = :error, "
                "finished_at = :now WHERE job_id = :job AND worker_id = :worker "
                "AND status = 'running'"
            ),
            {"status": status, "error": error, "now": now, "job": job_id, "worker": worker_id},
        )


def _to_job(model: JobModel) -> Job:
    return Job(
        id=model.id,
        job_type=model.job_type,
        payload=json.loads(model.payload) if model.payload else {},
        status=model.status,
        priority=model.priority,
        tenant_id=model.tenant_id,
        owner_user_id=model.owner_user_id,
        created_at=model.created_at,
        next_run_at=model.next_run_at,
        cron_expr=model.cron_expr,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        locked_until=model.locked_until,
    )
