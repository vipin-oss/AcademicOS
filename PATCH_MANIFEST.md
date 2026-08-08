# AcademicOS M13.1.1 — Incremental Patch Manifest (Corrective — QA Defect Fixes)

**Baseline:** `4f079a8` (M13.1) · **Commit:** `ae55aeb` · **Date:** 2026-08-08
**Scope:** corrective only — three production-critical QA defects. No new features, abstractions, persistence, memory, RAG or redesign.

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/tests/unit/test_grounded_qa.py` | 13 regression tests: streaming-leak (4), grounding (5), provenance (4). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/use_cases/ai/grounded_qa.py` | D1: leak-proof streaming (buffer + flush-on-completion + generation-failure fallback). D2: authoritative source-text injection via `DocumentAnnotationService`. D3: prompt-builder-driven provenance (`prompt_id`/`prompt_version`). Shared `_success_result` / `_fallback`; removes hardcoded prompt identity + double-verify bug. |
| `backend/app/api/routes/ai.py` | `POST /ai/qa` + `POST /ai/qa/stream` wire `annotation_service` + `storage` so QA answers from document content. |

## Defects closed

| # | Defect | Contract restored |
|---|---|---|
| 1 | Streaming QA leaked partial answers | Gateway failures / incomplete streams never expose a partial answer; tokens flushed only on confirmed completion; streaming fallback == sync honesty contract. |
| 2 | QA was not grounded (metadata-only prompt) | Authoritative document text reaches the generation prompt (reused intake pipeline); `AnswerVerifier` still verifies citations. |
| 3 | Provenance reported the wrong prompt identity | `prompt_id`/`prompt_version` are the values produced by the prompt builder (`assistant.default`), consistent across all paths. |

## Not changed (constraints honoured)
AI Core authority · transport ownership · 16 architecture guardrails · M11/M12 architecture · `QAResult` DTO shape (backward compatible) · no new feature flags · no new endpoints · no persistence.

## Verification
- Backend: **1462 passed, 2 skipped** (+13 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean on changed files
