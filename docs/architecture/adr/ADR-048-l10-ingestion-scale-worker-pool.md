# ADR-048 — L10 Ingestion Scale: worker pool + DLQ (L10)

**Status:** ratified at L10. Implements Freeze Contract §13.9 (L10 = Ingestion
Scale: worker pool, DLQ; prereq L2, consumed by L11) and SCALE_LAW (one stdlib
worker pool; no unmeasured infra).

## Context

The existing `IntakeJobManager` is a **single-dispatcher** FIFO worker
(``threading`` + ``queue.Queue``), with a durable worker lease, cooperative
pause/cancel, retry, resume, idempotency, per-item isolation, reconciliation
and the session-as-job-record contract. L10 scales ingestion by converting this
single dispatcher into a **bounded stdlib worker pool** behind the SAME job
semantics and method surface, and surfaces the existing failed/reconcile state
as a formal, queryable DLQ view.

## Decision

- **Worker pool:** `IntakeJobManager` gains a `max_workers` parameter (default
  ``1`` = the exact pre-L10 single-dispatcher behavior; configurable via
  ``settings.intake_max_workers``). It spawns ``max_workers`` dispatcher threads
  all consuming the same ``queue.Queue``. Durable worker leases, ownership
  verification after write, pause/cancel/shutdown, retry, resume, idempotency,
  per-item isolation and reconciliation are all preserved. A new
  ``active_session_ids()`` reports the full active set; ``active_session()``
  stays as the backward-compatible representative. Leases prevent duplicate
  execution across concurrent workers.
- **DLQ:** the existing FAILED-session and ERROR-item state is formalized as the
  L10 DLQ view (`ListDeadLetterUseCase` + `GET /intake/dead-letter`). It is
  **queryable and actionable**: failed sessions are resumable, failed items are
  retryable, and each entry carries the error/reason/attempts. **No second
  persistence system** — sessions and items remain the durable job records.
- **Infra constraint:** `threading` + `queue` only. No Kafka, Celery, Redis,
  Temporal, microservices, or a new database (SCALE_LAW forbids unmeasured
  infra). No migration.

## Rules

1. `max_workers=1` is the default and must reproduce the single-dispatcher
   behavior exactly.
2. A session is drained by at most one worker at a time (durable lease +
   ownership verification).
3. Pause/cancel/shutdown work correctly with multiple workers; in-flight drains
   persist their last checkpoint first.
4. Failed items remain isolated from healthy items; retry/resume stays explicit
   and deterministic (RETRY_LIMIT).
5. The DLQ surfaces existing state; it never creates a parallel persistence
   layer.

## Consequences

Ingestion scales horizontally within a process (bounded worker pool) with the
same correctness guarantees, and failures are surfaced as a queryable DLQ for
reconciliation. L11 consumes the same ingestion pipeline.
