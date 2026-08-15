# ADR-065 — V3 M18: accreditation workflow kernel

- **Status:** Accepted
- **Level:** V3 M18 (Accreditation) — the commercial differentiator
- **Supersedes:** nothing
- **Related:** ADR-032 (decision audit), A10 (authority boundary), blueprint §M18

## Context

NAAC · NBA · NIRF · IQAC/AQAR compliance needs a reproducible, source-cited,
locked reporting flow: criterion → indicator → evidence requirement →
submission → review → approval → period lock → export. The blueprint's hard
constraint: AI may suggest evidence and draft narratives, but may NEVER
approve evidence or lock a period.

## Decision

1. **Frameworks as data.** `accreditation_frameworks.py` registers NAAC / NBA
   / NIRF / IQAC(AQAR) with criteria and indicators (each with an evidence
   requirement). Additive data — a new framework is a row, never code.
2. **Workflow kernel.** `AccreditationWorkflow` + `accreditation_submissions`
   (migration 0025): draft → submitted → approved | rejected, then period
   LOCK (irreversible attestation). Reuses the L3 review discipline: approval
   is durable and attributable.
3. **Authority boundary is structural.** `approve()` requires a `reviewer`
   (human identity); `lock_period()` requires an approved submission AND a
   `locked_by` human. `suggest_evidence()` is a store-free static method — it
   CANNOT mutate state, so AI suggestion can never become approval or lock by
   construction (A10).

## Consequences

**Positive**
- A reproducible, auditable accreditation flow with an irreversible period lock.
- The "AI never approves" boundary is enforced by the API, not by convention.
- Frameworks extend without code.

**Negative / deferred**
- Export (report generation from locked periods) is the next step; the kernel
  records the state export will render from (source-cited, locked).
- The review UI is frontend (M14 work); the backend contract is complete.

**Revisit when:** export/PDF generation for a locked period is needed — render
from `for_framework()` submissions, which are immutable once locked.
