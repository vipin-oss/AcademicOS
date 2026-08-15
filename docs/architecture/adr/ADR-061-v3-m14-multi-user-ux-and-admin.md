# ADR-061 — V3 M14: multi-user UX & admin (roles + operational panel)

- **Status:** Accepted
- **Level:** V3 M14 (Multi-User UX & Admin)
- **Supersedes:** nothing
- **Related:** ADR-056 (M9 deny-by-default), M3 (tenancy stamping), M7 (extraction health), M10 (jobs), M12 (spend)

## Context

The blueprint wants role-aware navigation (Professor / Scholar / HoD / Admin),
shared-vs-private scoping, an admin panel (users, roles, extraction health, job
queue, spend, storage), and notification delivery (in-app always, email
optional, digest batching).

## Decision

1. **Four role classes.** `UserRole` gains `professor` / `scholar` / `hod`
   (ADMIN already existed). `RoleBasedPermissionEvaluator` maps the academic
   roles to READ + WRITE (never MANAGE) — the administrative capability stays
   admin-only, so role escalation is impossible by enum/policy.
2. **Admin panel backend contract.** A MANAGE-gated `/admin` router exposes the
   operational views the panel needs: job queue counts, spend totals (from the
   M12 ledger), storage usage, and extraction health (from M7). User/role
   management already exists on `/auth` (`list_users` + `assign_user_roles`,
   both MANAGE-gated).
3. **Scoping + notifications are already present.** Shared-vs-private scoping
   is the existing ACL (`acl_scope` readers/writers/managers, enforced by M9's
   deny-by-default evaluator). In-app notifications already exist (productivity
   module); email/digest are deferred (no SMTP in R1, verified).
4. **Frontend is deferred.** Role-aware navigation and the full UX-state matrix
   are frontend work; this ADR ships the backend contracts (roles + admin
   views) the frontend consumes.

## Consequences

**Positive**
- Roles are closed and escalation-proof; the admin panel has real backend
  views to render.
- Reuses existing scoping/notifications — no duplicate subsystems.

**Negative / deferred**
- Role-aware navigation, command palette, and the UX-state matrix are
  frontend (M14 frontend work, deferred with the cookie-session migration
  from ADR-056).
- Email/digest notification delivery remains deferred (no SMTP transport).

**Revisit when:** the frontend multi-user shell is built — wire role-aware
navigation over these roles and the admin panel over `/admin`.
