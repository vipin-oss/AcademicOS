"""Durable job worker process (V3 M10, ADR-057).

A standalone process that claims jobs from the durable ``jobs`` queue and runs
them, separate from the API process (the API only submits). Runs forever:
reap stale leases -> claim the next due job (bounded by backpressure) ->
dispatch to a handler by job type -> complete/fail. At-least-once with
idempotent handlers; a crash mid-job leaves the lease to be reaped.

Usage (from backend/):
    python scripts/worker.py
"""

from __future__ import annotations

import datetime as dt
import time

from app.application.services.backpressure import BackpressureLimiter
from app.core.config import settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.persistence.job_store import SQLJobStore

#: Poll interval (seconds) when no job is claimable.
_POLL_SECONDS = 0.5


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _run_job(job) -> tuple[bool, str | None]:
    """Dispatch a job by type. Returns (ok, error).

    Handlers are registered additively here; the skeleton ships a no-op for
    generic types and a dossier-rebuild handler as the first real consumer.
    """
    from app.application.services.fact_cache import invalidate_facts

    if job.job_type == "dossier_rebuild":
        # Rebuild the cached dossier aggregate: the cheapest correct handler —
        # invalidate so the next read recomputes from authoritative state.
        invalidate_facts()
        return True, None
    # extraction / embedding / export / digest / scheduled: no-op skeletons
    # (the real handlers wire into the existing extraction/search services).
    return True, None


def main() -> None:
    limiter = BackpressureLimiter(
        global_limit=settings.job_global_concurrency,
        per_user_limit=settings.job_per_user_quota,
        per_type_limit=settings.job_per_type_concurrency,
    )
    worker_id = f"worker:{settings.app_name}:{__import__('os').getpid()}"

    while True:
        try:
            db = SessionLocal()
            try:
                store = SQLJobStore(db)
                store.reap_stale(now=_utcnow_iso())
                job = store.claim_next(worker_id, now=_utcnow_iso())
                if job is None:
                    time.sleep(_POLL_SECONDS)
                    continue
                if not limiter.allow(
                    job_id=job.id, job_type=job.job_type, owner_user_id=job.owner_user_id
                ):
                    # release immediately; the lease will re-trigger later
                    store.fail(job.id, worker_id=worker_id, now=_utcnow_iso(), error="backpressure")
                    continue
                limiter.start(job_id=job.id, job_type=job.job_type, owner_user_id=job.owner_user_id)
                ok, error = _run_job(job)
                if ok:
                    store.complete(job.id, worker_id=worker_id, now=_utcnow_iso())
                else:
                    store.fail(job.id, worker_id=worker_id, now=_utcnow_iso(), error=error or "failed")
                limiter.finish(job_id=job.id, job_type=job.job_type, owner_user_id=job.owner_user_id)
            finally:
                db.close()
        except KeyboardInterrupt:
            break
        except Exception:  # noqa: BLE001 - worker must survive transient errors
            time.sleep(_POLL_SECONDS)


if __name__ == "__main__":
    main()
