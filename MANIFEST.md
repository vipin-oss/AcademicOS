# AcademicOS — L3 Human-in-the-Loop (Confirmation / Correction)

**Scope:** the L3 HITL confirmation/correction layer (ADR-032..034) on top of the
committed L1 knowledge-plane and L2 document-intelligence layers. Deterministic,
ACL-safe, auditable. No planner/retrieval/agent/frontend/OCR work.

## What this milestone establishes
- **Extraction→claim bridge (ADR-034):** deterministic predicate-driven
  `NirMapper.write_claims` + `fact_extraction.py`; the orchestrator now proposes
  PROPOSED claims (with polymorphic spans, confidence, acl_scope) during
  ingestion for both documents and package members. Claims stay PROPOSED,
  distinct from human-confirmed facts.
- **Confirmation/correction queue (ADR-032/033):** `ConfirmationQueueService`
  (triaged by confidence + OCR, paginated, ACL-filtered), `ClaimConfirmationService`
  (approve/reject/correct), `CdmConfirmationService` (CDM-block approve/reject).
- **Corrections as data:** `ClaimService.correct` creates a new ASSERTED claim
  that SUPERSEDES the candidate (ADR-021) — never destructive.
- **Decision audit:** `claim_decisions` + `cdm_decisions` tables (append-only,
  idempotent by `decision_id`, reviewer/previous/resulting status, notes,
  acl_scope, eval_run_id). Claim-scoped — NOT coupled to conversation reviews.
- **ACL:** confirmation actions gated by `reviewer_can_decide` (owner/writer/
  manager); legacy null-scope candidates open-by-default (Freeze Contract
  ADR-017 note).
- **API (ADR-022):** `/confirmations/pending`, `/approve`, `/reject`, `/correct`,
  `/decisions`, `/cdm/{block}/approve|reject` — all additive; existing
  `/claims`/`/cdm` routes preserved.
- **Migration 0013:** `claim_decisions` + `cdm_decisions` (additive, reversible).
- **L2 closed:** LEVELS.md L2 `done`, L3 `in_progress`; ADR-032..034 ratified.

## Verification
Backend pytest: 2038 passed, 2 skipped (includes 30 new L3 tests + guardrails).
Frontend vitest: 101 passed. tsc --noEmit: clean. git diff --check: clean.
L0/L1/L2/memory-fix/patch-farm boundaries unchanged.
