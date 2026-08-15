# ADR-055 — V3 M8: retrieval speed, parallel fan-out, and the fact/dossier cache

- **Status:** Accepted
- **Level:** V3 M8 (Retrieval Speed & Parallelism)
- **Supersedes:** nothing
- **Related:** ADR-005/A5 (no async conversion), SCALE_LAW, blueprint law 22 (one invalidation mechanism), M5 (rung 0), M10 (relay.py)

## Context

Blueprint M8 makes retrieval measurably faster without changing its contract.
Audit A5 established that a sync driver (`psycopg2` + sync Session) makes an
async conversion harmful, so parallelism must be a bounded threadpool inside
sync handlers — no driver change, no session rewrite.

## Decision

1. **Parallel fan-out (bounded, flag-gated).** The search semantic leg
   (embedder + vector repository — never touches the DB session) runs on a
   bounded `ThreadPoolExecutor` while the lexical leg runs on the request
   thread. Results are bit-identical to the sequential path (the leg builder
   is deterministic and self-contained). Feature-flag `search_parallel_enabled`
   (default on) is the rollback.
2. **In-process fact/dossier cache (bounded LRU, law 22).** A bounded
   thread-safe LRU (`FactCache`) caches rung-0 confirmed-claim lookups and
   dossier aggregates. It is invalidated by the SAME authoritative write paths:
   the claim store (facts change on confirm/reject/correct/supersede) and the
   outbox applier (object/projection changes). Memory is bounded (`DEFAULT_CAPACITY`),
   never unbounded (SCALE_LAW).
3. **Dossier aggregates (rung 1).** `DossierService` computes the common
   "how many / how much" aggregates over the authoritative repositories and
   caches them. This is the always-available form; the materialized-table
   form (rebuilt by outbox consumers) is the scale-time upgrade behind the
   same invalidation law, so the swap is invisible to callers.
4. **Read-time outbox drain is retained (reconciled).** The blueprint directs
   removing the `/search` read-time drain and replacing it with "the
   continuously-running relay". Repository evidence shows the continuously-
   running relay is M10's `relay.py` (a separate process) — an M10
   deliverable. Removing the drain before that process exists would break the
   M14.1 freshness contract pinned by `test_search_read_repair.py`
   ("new document searchable without manual sync"). So the read-time drain
   stays (it is already a cheap, idempotent no-op once drained); the relay
   substitution rides M10.
5. **Full-table `repository.list()` calls are left untouched (reconciled).**
   The eight verified calls live in the frozen legacy `rules-v1` assistant
   provider (7) and the off-hot-path rebuild (1). Modifying frozen legacy
   code is an anti-patch violation (ADR-020); these are not on the active
   search/retrieval hot path. No change.

## Consequences

**Positive**
- Retrieval parallelism with zero result change and zero driver/session risk.
- A bounded, correctly-invalidated cache delivers the rung-0/rung-1 latency
  win without unbounded memory or stale reads.
- No async conversion, no new queue, no new database (SCALE_LAW honoured).

**Negative / deferred**
- The read-time drain remains until M10 ships `relay.py` (documented; the
  drain is already cheap).
- The dossier is cached-computed, not yet a materialized table; the table form
  is the scale-time upgrade.

**Revisit when:** M10's `relay.py` lands — then retire the read-time drain in
`/search`; and when rung-1 aggregates become a hot path at scale — then
materialize the dossier behind the outbox consumer.
