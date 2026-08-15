# ADR-062 — V3 M15: multi-tenant isolation

- **Status:** Accepted
- **Level:** V3 M15 (Multi-Tenant Isolation)
- **Supersedes:** nothing
- **Related:** M3 (tenant stamping), M9 (deny-by-default + tenant flag), M12 (spend), ADR-056

## Context

The blueprint wants organizations, hierarchy, memberships, scoped roles, RLS
as defense-in-depth, per-tenant storage quota + spend cap, and a tenant
lifecycle (create / suspend / export / delete) — with enforcement as "a config
flip because M3 stamped and M9 enforced".

## Decision

1. **Organizations are tenants.** `organizations` (migration 0022) carries the
   lifecycle status and per-tenant `storage_quota_bytes` + `spend_cap_usd`;
   `memberships` binds a user to an organization with a scoped role.
2. **Isolation is stamp-based.** The M3 `tenant_id` stamp on every table is
   the isolation key. Query compilers (saved views) put the tenant predicate
   first in WHERE (authorization before aggregation); search scopes by the
   M9 evaluator + the M9 `security_tenant_enforcement` flag. Enforcement is a
   flag, never a migration.
3. **Tenant lifecycle.** `TenantService` (application) + a MANAGE-gated
   `/admin/tenants` surface: create / suspend / resume / list / add-member /
   list-members. Suspension denies the tenant's members (access gate) without
   deleting data; export/delete are deferred (delete is destructive and needs
   the backup/restore rehearsal from M3's acceptance).
4. **RLS is defense-in-depth.** PostgreSQL Row-Level Security is the second
   boundary behind app checks (tenant predicates + the evaluator); it is
   documented, not the primary mechanism (the app layer already filters).

## Consequences

**Positive**
- Two-tenant isolation is provable (isolation matrix test) and enforced by
  existing stamping + flags — no rewrite.
- Per-tenant quota/cap are first-class rows, wired into M12 spend + storage.

**Negative / deferred**
- Hierarchy (parent/child organizations) and scoped roles beyond
  member/role are deferred; the membership `role` field is the extension seam.
- Tenant export/delete are deferred pending the backup/restore rehearsal.
- RLS DDL is documented, not yet emitted (Postgres-only, CI-exercised when
  the Postgres job runs the full schema).

**Revisit when:** the destructive tenant lifecycle (delete/export) is needed —
add it behind the backup/restore drill; and when hierarchy is needed — add a
`parent_id` to `organizations` (additive).
