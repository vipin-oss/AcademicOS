# ADR-026 — acl_scope source and propagation (L1)

**Status:** ratified at L1. Implements Freeze-Contract ADR-009 ("every derived
artifact carries the source's acl_scope") and the ADR-017 minimum stamping
rule. Resolves the minimal slice of OPEN_DECISIONS Q1 (workspace/tenant) and
Q8 (role-context ACL) required for L1.

## Decision

1. **Source:** the `acl_scope` of every derived row is the **source object's own
   ACL scope** (`object_acl_scope`, i.e. owner + readers + writers + managers),
   stamped at write time by the single index consumer (ADR-009) and recomputed
   on ACL change.
2. **Semantics:** preserve the existing **stricter-of-endpoints** behavior used
   by relationships. We do **not** invent role-union semantics — that is
   deferred to L9/L12 behind the isolation matrix.
3. **Coverage:** search_documents, document_contents, document_chunks,
   document_search_fts, claims, claim_spans, cdm_blocks all carry
   `acl_scope`.
4. **Tenancy (Q1):** acl_scope is a single owner-derived scope string today;
   multi-workspace partitioning is deferred to L12 (ADR-017: stamp now,
   partition later). The column format widens additively, not a schema rewrite.
5. **Role-context (Q8):** the role-union evaluation semantics are deferred;
   L1 keeps the deterministic stricter-of propagation.

## Consequences

Retrieval/evidence can pre-filter by `acl_scope` without a second object
lookup, satisfying the isolation matrix. No role-union invention.
