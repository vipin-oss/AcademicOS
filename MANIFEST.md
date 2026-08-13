# AcademicOS — L6 Evidence & Citation Extension — Delivery Manifest

**Level:** L6 — Evidence & Citation Extension
**Commit:** `b79c296d62badd7127e152609f2dca80a21f5981`
**Parent:** `d9c0ad09ba49d707090fc3fac74bd38abf80e878` (L5 authoritative baseline)
**Commit message:** `feat(l6): add evidence and citation extension`

## Scope
L6 adds the evidence & citation extension: fact/claim citations from the L1
claim store, source-span preservation (incl. the approved L3 `confirm()`
prerequisite span-preservation fix), CONFIRMED/ASSERTED eligibility,
deterministic citation ordering/dedup, ACL/principal filtering, a confidence
output contract (extraction vs fact), evidence-set traceability, an L6
evaluation gate, and L6 architecture guardrails (ADR-039 / ADR-040).

Reuses existing `CitationBuilder`, `AnswerVerifier`, `evidence_assembly`,
`ClaimStore`, `Span`, `Claim.is_authoritative`, `object_acl_scope` /
`PermissionEvaluator`, and the L5 tool/audit layer. No second planner,
retrieval system, citation verifier, ACL system, capability registry, or tool
system was created. No migration was required (alembic head remains `0014`).

## ZIP entries (repo-relative paths)
1. `MANIFEST.md`
2. `backend/app/api/routes/evidence.py`
3. `backend/app/application/dtos/evidence.py`
4. `backend/app/application/services/claim_evidence.py`
5. `backend/app/application/services/claim_service.py`
6. `backend/app/main.py`
7. `backend/app/tests/architecture/test_l6_guardrails.py`
8. `backend/app/tests/eval/test_l6_eval_gate.py`
9. `backend/app/tests/integration/test_l6_evidence_api.py`
10. `backend/app/tests/unit/test_claim_store.py`
11. `backend/app/tests/unit/test_l6_claim_evidence.py`
12. `docs/architecture/LEVELS.md`
13. `docs/architecture/adr/ADR-039-fact-citation-evidence-contract.md`
14. `docs/architecture/adr/ADR-040-l6-evaluation-gate.md`
15. `docs/architecture/adr/README.md`

This matches exactly the L6 commit diff (`git diff d9c0ad0..HEAD`) plus
`MANIFEST.md`.

## Test results (verified in the commit environment)
- **L6 tests** (unit + integration + eval gate + architecture guardrails): **16 passed**
- **L5 focused tests** (tool / ACL / executor / registry / permission): **129 passed**
- **L1–L4 claim/span/evidence regression** (claim, span, evidence, confirmation, decision): **144 passed**
- **Intake module (in isolation):** **11 passed** (pre-existing pause/resume timing
  test, unrelated to L6, passes when run in isolation)
- **Full backend suite:** documented at `2108–2109 passed, 2 skipped` for the
  non-intake portion plus `11 passed` for intake in isolation. The only
  full-suite failure is the pre-existing flaky/timing
  `test_intake_queue_api.py::TestPauseResumeRestart::test_finished_items_are_never_restarted`
  (classification D — flaky; passes in isolation). 2 skips are PostgreSQL-only
  JSONB cases (environment C).
- `git diff --check`: clean. `git diff --cached --check`: clean.

## Frozen-boundary status
- No L0/L1/L2/L4/L5 frozen source files changed, except the **approved L3**
  `backend/app/application/services/claim_service.py` span-preservation fix
  (2 lines) required by the L6 fact-citation contract.
- Alembic migration head remains **`0014_tool_call_log.py`** (no migration 0015).
- `dffba2a` / `container_policy.py` security fix: NOT touched (out of scope).
