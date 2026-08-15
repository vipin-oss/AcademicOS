# ADR-056 — V3 M9: deny-by-default security posture, pre-filter, revocation

- **Status:** Accepted
- **Level:** V3 M9 (Security: Deny-by-Default) 🔒 hard gate
- **Supersedes:** nothing
- **Related:** ADR-009/026 (acl_scope), M3 (tenancy stamping), blueprint §M9, SRS §3.2/3.3

## Context

R1 shipped three verified fail-open holes: `object_acl` allowed when an ACL
was missing, `role_based` granted READ+WRITE to roleless principals, and
`search` ranked over unauthorized data before filtering (ACL after top-k).
M9 closes them.

## Decision

1. **Deny-by-default is posture-gated.** `ObjectPermissionEvaluator` and
   `RoleBasedPermissionEvaluator` gain a `deny_by_default` flag, defaulting to
   the `security_deny_by_default` setting (OFF). When ON: missing/malformed
   ACL denies, owner-only ACL grants only owner+admin, roleless principals
   hold nothing. **The flag only moves fail-open → fail-closed** — there is no
   code path that restores fail-open (security rollback is impossible by
   construction). The flag is OFF by default to preserve the single-user
   M1-M5 status quo; it is flipped ON as the blueprint's "second human" hard
   gate, and the leak-matrix suite gates that flip.
2. **Search pre-filter, never post-filter.** `SearchObjectsUseCase` now
   over-fetches candidates, authorizes them against the live objects (R4
   evaluator) *before* reciprocal-rank fusion, and ranks only the authorized
   set. Unauthorized or vanished objects are never ranked, never leaked, and
   can no longer crowd authorized results out of the top-k.
3. **Server-side principal.** `PrincipalContext` (sub + roles + tenant) is
   built only from the live USER object (`get_roles`), never from token
   claims — roles and tenant cannot be forged client-side.
4. **Token revocation.** Tokens carry a `jti`; `POST /auth/logout` writes it
   to a durable `session_revocations` denylist (idempotent, pruned past the
   token's absolute expiry). Authentication rejects a revoked token even
   before its `exp`.
5. **Tenant enforcement is flag-gated** (`security_tenant_enforcement`, OFF).
   M3 stamped `tenant_id` on every table; enforcement filters by the
   principal's tenant once multi-tenancy is real (M15). The flag is the seam;
   full wiring lands with M15's tenancy work.

## Consequences

**Positive**
- The three verified holes are closed behind a single, monotonic posture flag.
- Search no longer ranks over unauthorized data (recall + non-leakage).
- Revocation is durable and testable end-to-end.

**Negative / deferred**
- The cookie/session transport migration (HttpOnly + Secure cookies, rotation,
  idle-expiry, dropping `frontend/src/lib/auth/token.ts`) is a frontend +
  auth-schema change: this ADR ships the backend revocation + principal
  foundation it requires, and defers the cookie/frontend migration to the
  multi-user frontend work (M14). Bearer-token absolute expiry remains.
- Tenant enforcement is a flag, not yet wired into every list/count/export
  (that is M15 tenancy work; the flag + stamping make it a flip, not a
  migration).

**Revisit when:** the second user is admitted — flip `security_deny_by_default`
ON and run the leak matrix; and at M14 — migrate the frontend to cookie
sessions over the revocation store.
