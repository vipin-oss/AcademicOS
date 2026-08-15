# ADR-047 — Q5 claim-store scaling decision (L9, measured)

**Status:** ratified at L9. Resolves Freeze Contract §13.12 **Q5** ("claim-store
scaling — decide at L9 with measurements") using actual measurements of the
existing claim store, per SCALE_LAW (measured evidence, no unmeasured infra).

## Decision

Q5 is resolved at L9 by **measurement**: the current claim-store architecture is
**acceptable** at the evaluated scale points, and **no architectural change is
required now**. Scaling mechanisms, if ever needed, belong to L10+ (per the
SCALE_LAW planned-mechanisms table) and remain deferred until measured need.

## Measured behavior

Measurement methodology (in-memory SQLite, `SQLClaimStore`, deterministic
operations; warm-up excluded; the L9 `test_l9_scale_budgets.py` records the
CI-safe checks):

| Operation | N=1,000 | N=10,000 | Observation |
|---|---|---|---|
| `propose`/`put` (insert) | ~1.15 ms/claim | ~1.10 ms/claim | linear in N (expected for append) |
| `get` (by claim_id) | ~0.38 ms/claim | ~0.38 ms/claim | O(1) — claim_id idempotency key indexed |
| `by_source` (scoped to a document) | ~0.45 ms/doc | ~2.7 ms/doc (10k claims/100 docs) | source-scoped, stable per source |

## Analysis / bottleneck

- **Current architecture:** `SQLClaimStore` persists claims in a dedicated
  `claims` table with `claim_id` as the idempotency key and polymorphic
  `claim_spans` rows; reads are `claim_id` (O(1)) or `source_document_id`-scoped
  (bounded per source). Claims are written by engines and read by the
  confirmation queue / evidence layer, all ACL-scoped.
- **Observed bottleneck:** none at the evaluated scale (1k–10k). Writes are
  linear (inherent), reads are indexed/scoped and constant. There is **no O(N)
  full-scan** in the measured operations.
- **Acceptability:** the current architecture meets the evaluated scale points
  with bounded, indexed reads; the linear write cost is the expected baseline
  and not a defect.

## Recommended decision for Q5

- Current claim-store architecture: **acceptable**.
- Scaling work required now: **none**.
- Recommended Q5 decision: **defer any claim-store scaling mechanism to L10+**
  (partitioning/shards per SCALE_LAW) and trigger only on measured need at the
  production 1M scale; do not redesign the claim store at L9.

## Consequence / recording

- `OPEN_DECISIONS.md` Q5 is updated to reflect the measured decision (recorded
  here; the code path is unchanged).
- No migration, no schema change, no production claim-store modification at L9.
