# ADR-057 — V3 M10: durable jobs + separate worker/relay processes

- **Status:** Accepted
- **Level:** V3 M10 (Durable Jobs & Worker Process)
- **Supersedes:** nothing
- **Related:** ADR-048 (L10 worker pool), ADR-055 (relay deferral), SCALE_LAW, blueprint §M10

## Context

R1's intake semantics are already correct (lease, heartbeat, resume, DLQ,
per-item isolation); only the substrate is wrong — a `queue.Queue` + threads
*inside* the API process. M10 moves processing to a durable queue with a
separate worker/relay process so work survives restarts and 1000-document
batches run unattended.

## Decision

1. **One generic durable queue.** `jobs` + `job_attempts` tables (migration
   0018) carry generic job types (extraction, embedding, dossier rebuild,
   export, digest, scheduled) with priority, recurrence (`next_run_at` /
   `cron_expr`), and lease (`locked_until`). No per-type subsystem, no new
   queue/event-bus (SCALE_LAW).
2. **At-least-once claim.** `SQLJobStore.claim_next` claims exactly one due
   job via `SELECT … FOR UPDATE SKIP LOCKED` on PostgreSQL and an atomic
   conditional lease on SQLite; `reap_stale` releases crashed workers' leases;
   `attempts`/`max_attempts` bound retries; every completion/failure writes a
   `job_attempts` audit row.
3. **Separate processes.** `scripts/worker.py` (claim → dispatch → complete/
   fail, bounded by `BackpressureLimiter`) and `scripts/relay.py` (drain the
   outbox into the search projection on an interval — the "continuously-
   running relay" ADR-055 deferred). The API only submits. The in-process
   `IntakeJobManager` is retained behind `durable_jobs_enabled` as the rollback.
4. **Backpressure.** `BackpressureLimiter` enforces a global cap, a per-user
   quota, and a per-type concurrency cap (config-driven).

## Consequences

**Positive**
- Processing survives process/DB restarts (durable queue + lease reaping).
- The outbox → search relay exists as a process, enabling ADR-055's read-time
  drain retirement.
- Generic queue: future job types are additive rows, not new infrastructure.

**Negative / deferred**
- The worker dispatches job types to handlers; extraction/embedding/export
  handlers are no-op skeletons until they are wired into the existing
  extraction/search services (dossier_rebuild is the first real handler).
- Recurrence (`cron_expr`) is queued and returned by `scheduler_due`; the
  worker's re-enqueue loop for cron is a thin follow-up.
- `FOR UPDATE SKIP LOCKED` is exercised on PostgreSQL in CI; SQLite uses the
  atomic-lease equivalent (tested).

**Revisit when:** a measurement shows the in-process worker pool is the
bottleneck at scale — then run `worker.py`/`relay.py` as the durable backend
(the flip is `durable_jobs_enabled`).
