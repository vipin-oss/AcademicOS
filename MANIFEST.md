# AcademicOS — L4 Query Understanding v2

**Scope:** the L4 model-driven query-understanding layer (ADR-035/036) on top of
the committed L0-L3 baseline. Model-driven planner → deterministic validation →
frozen ≤15-command fast-path → clarify/refuse → dispatch. Active assistant path
no longer regex-routes intents (ADR-020).

## What this milestone establishes
- **Plan schema (ADR-035):** `Plan` DTO matching Freeze Contract §16
  (`operation, domains[], entities[], time_range, filters{}, output_kind,
  evidence_required, sub_plans[]`); `PlanValidator` (deterministic, bounded,
  operation ∈ frozen capability registry).
- **Planner:** `PlannerService` calls `AiCore.gateway().structured_generate()`
  (ADR-001) with the frozen plan JSON schema; model output is untrusted and
  always validated before dispatch.
- **Frozen fast-path (ADR-036):** `FAST_PATH_COMMANDS` — exactly 15 commands,
  cannot grow (guardrail-pinned). `FastPathExecutor` + offline keyword router.
- **Clarify/refuse:** `ClarifyRefuse` produces explicit machine-readable
  outcomes (never generic assistant text).
- **QueryUnderstanding orchestration:** planner → validate → fast-path /
  clarify / refuse; never executes raw model output.
- **Active path (ADR-020):** `QueryUnderstandingAssistantProvider` + rewired
  `provider_factory`; the active assistant answering path no longer uses
  `parse_question`/`rules-v1` regex routing. A deterministic offline answer
  seam (fast-path executor) preserves offline data answering.
- **API (ADR-022):** `POST /plans` + `POST /plans/validate` (additive);
  existing assistant routes preserved.
- **L4 eval gate:** golden `gate_level="l4"` cases resolve to deterministic
  outcomes (reuses the frozen L0 capability framework, unmodified).
- **Milestone:** LEVELS L3 `done`, L4 `in_progress`; ADR-035/036 ratified.

## Verification
Backend pytest: 2075 passed, 2 skipped (includes 37 L4 tests + restored L2
fixtures). Frontend vitest: 101 passed. tsc: clean. Architecture guardrails:
77 passed. git diff --check: clean. No new migrations (0013 head unchanged).
L0/L1/L2/L3/memory-fix boundaries unchanged.

## Note
`backend/app/tests/unit/extraction_fixtures.py` was restored with the missing
L2 fixture builders (make_xlsx_bytes etc.) from the authoritative L2 artifact —
the committed tree was missing them; the committed L2/L3 tests reference them.
