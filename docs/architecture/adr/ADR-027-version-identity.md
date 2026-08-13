# ADR-027 — Path-agnostic version identity (L1)

**Status:** ratified at L1. Implements the version/replacement slice of
ADR-021 ("a newer file version supersedes derived knowledge from the previous
version") and the minimal slice of OPEN_DECISIONS Q10 (direct-upload/intake
merge timing).

## Decision

1. **Version identity is path-agnostic:** a document's "new version" is defined
   by an explicit new object version (and/or distinct normalized content), NOT
   by which ingestion path (direct upload vs intake) delivered it.
2. **Duplicate vs version (ADR-002b / ADR-021):** an upload of identical
   normalized content remains a content-identity duplicate link (canonical
   registry, never merged). A new file version (distinct content or explicit
   new version) triggers the supersession cascade.
3. **Cascade (ADR-021):** on a new version, old CDM blocks and old
   PROPOSED/CONFIRMED claims of the previous version are SUPERSEDED (never
   deleted), and re-extraction (an L2 engine) proposes the new values. Nothing
   is silently merged.
4. **Direct-upload/intake merge (Q10):** the two ingestion paths are left as-is
   for L1; merging their mechanics is deferred to L2/L10. The cascade and
   identity rule are shared and path-agnostic.

## Consequences

A revised sanction letter cannot leave the old sanctioned amount standing as
current; as-of queries keep the supersede chain. Q10's merge timing is not
resolved by L1 (left deferred), only the version-identity rule that both paths
share is fixed.
