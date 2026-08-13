# ADR-022 — API contract freeze for new surfaces (M-4)

**Status:** law recorded at L0. **No new API** is introduced in L0.
OpenAPI for claims / CDM / confirmation / plans / tools ships at L1.

## Decision

For every **new** L1+ surface:

1. An **OpenAPI** contract is published with the surface.
2. The frontend consumes **only** those contracted APIs.
3. A contract change requires an **ADR amendment** (impact analysis),
   not a silent field rename.

## Rules

- Existing routes are unchanged by L0.
- L1 freezes contracts before L2/L3 UI is written against them.
- Additive fields are preferred over breaking changes.

## Consequences

Frontend and backend cannot drift on claims, CDM, confirmation, plans,
or tools during L2/L3.
