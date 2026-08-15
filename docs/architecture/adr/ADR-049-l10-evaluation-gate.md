# ADR-049 — L10 evaluation gate (L10)

**Status:** ratified at L10. Activates an L10 evaluation gate for the intake
worker pool + DLQ (ADR-048), reusing the existing evaluation and performance
methodology (the L9 eval framework and `test_search_perf_smoke` conventions).
No second evaluation framework, no new capability ID, no frozen L0–L9
evaluation change.

## Decision

L10 adds:

- **`test_l10_eval_gate.py`** — verifies real worker-pool/DLQ behavior:
  bounded worker pool, lease-based no-duplicate-execution, concurrent independent
  sessions, one-failing-item-does-not-block-healthy-items, bounded retries,
  no duplicate terminal completion, DLQ surfacing, resume/idempotency.
- **`test_l10_guardrails.py`** — pins: reuse stdlib only (no Kafka/Celery/etc.),
  no new capability ID, no frozen L0–L9 change, no migration, DLQ reuses existing
  state, backward-compatible `max_workers=1`.
- **`test_intake_worker_pool.py`** — worker-pool + DLQ integration tests.
- **`test_l10_scale_budgets.py`** — bounded CI-safe ingestion scale checks
  (1k/10k sessions/items) measuring actual behavior; larger 100k/1M marked
  CI-optional per SCALE_LAW.

## Rules

1. Reuse the existing L9 eval framework and the `test_search_perf_smoke`
   performance methodology (warm-up excluded, generous CI-safe bounds).
2. The gate tests actual worker-pool/DLQ behavior, not mock-only behavior.
3. No new capability ID; the frozen 18-capability registry is unchanged.
4. No modification to the frozen L0–L9 evaluation architecture.

## Consequences

L10 ingestion-scale behavior (concurrency, isolation, DLQ, budgets) is verified
at the capability level consistent with the anti-patch and capability-evaluation
doctrine.
