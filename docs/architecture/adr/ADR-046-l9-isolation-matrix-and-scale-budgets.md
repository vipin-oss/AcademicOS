# ADR-046 — L9 isolation matrix & scale budgets (L9)

**Status:** ratified at L9. Implements Freeze Contract §13.8.4 (isolation matrix
green; latency budgets at synthetic 1k/10k/100k/1M corpora), §13.11 (isolation
matrix green for data-touching paths; performance budgets measured), and
SCALE_LAW.md (measured evidence; no unmeasured infra).

## Context

The L9 evaluation layer requires (a) an **isolation matrix** verifying that
capability boundaries remain isolated and no forbidden cross-level
dependency/leakage exists, and (b) **scale/latency budgets** grounded in the
existing SCALE_LAW and repository contracts. The existing `test_search_perf_smoke`
establishes the deterministic-perf methodology; L9 generalizes it.

## Decision — Isolation matrix

`test_l9_isolation_matrix.py` verifies, deterministically, that:
- cross-principal ACL isolation holds across data-touching paths (retrieval,
  tools, claims/evidence, persistent memory, cross-domain);
- no capability boundary leaks another capability's data;
- memory is never treated as evidence (ADR-015);
- a denied principal never receives content it cannot read (pre-filter, never
  post-filter);
- graph-neighbor-only results are never citable (Freeze §20/§21).

## Decision — Scale budgets

`test_l9_scale_budgets.py` separates:
- **A. deterministic CI-safe scale checks** — synthetic corpora at **1k** and
  **10k** objects/claims with deterministic operations (claim-store put/get/
  by_source, tool count/inventory, search smoke), recording p95 latency and
  result sanity, with generous CI-safe bounds;
- **B. larger performance/measurement checks** — **100k / 1M** marked
  CI-optional (skipped in normal runs) per SCALE_LAW, exposing the measurement
  path for recorded budget verification without running heavy workloads every
  invocation.

Every budget defines: dataset/corpus assumptions, the operation measured, the
latency/throughput metric, memory/resource metric where appropriate, acceptable
budget, measurement methodology, pass/fail rule, and reproducibility
requirements. Thresholds are grounded in SCALE_LAW / Freeze Contract / actual
measurements — not arbitrary numbers.

## Rules

1. Reuse the `test_search_perf_smoke` methodology (warm-up excluded, p95, result
   sanity, generous CI-safe bounds).
2. No unmeasured infra: scale thresholds come from recorded measurements.
3. The larger (100k/1M) checks are separate and CI-optional.
4. No production behavior is changed to make budgets pass.

## Consequences

L9 provides a reproducible isolation matrix and scale-budget suite that gate
releases without introducing unmeasured infrastructure.
