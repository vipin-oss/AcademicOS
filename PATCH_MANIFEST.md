# AcademicOS M13.3.1 — Incremental Patch Manifest (Corrective — Related Documents Defects)

**Baseline:** `7d93a39` (M13.3) · **Commit:** `836d60d` · **Date:** 2026-08-08
**Scope:** corrective only — two M13.3 audit defects. No new abstractions, no architecture change, no `/search` contract change.

## Files Changed

| Path | Change |
|---|---|
| `backend/app/api/routes/ai.py` | DEFECT-1: `/ai/related` resolves `embedder`/`vector_repository` **inline after the gate** (removed from the `Depends()` signature) so a disabled feature never resolves the AI embedder nor touches the vector store. Uses the SAME `get_embedder`/`get_vector_repository` as `/search`. |
| `backend/app/application/use_cases/ai/related_documents.py` | DEFECT-2: source must be `ObjectType.DOCUMENT` (`ValidationError` after READ); candidates filtered to documents via the authoritative object. |
| `backend/app/tests/integration/test_ai_related_api.py` | DEFECT-1 regression: embedder/vector NOT resolved when `related_documents=false` or `AI_ENABLED=false`; resolved only when enabled; `/search`-unchanged smoke test. |
| `backend/app/tests/unit/test_related_documents.py` | DEFECT-2 regression: non-document source rejected; non-document candidate excluded; document candidate returned; permission/self-exclusion/ordering intact with the type filter. |

## Defect mechanism
- **Defect 1:** FastAPI resolves signature `Depends()` before the handler body, so the gate (in the body) ran after the embedder/vector were already resolved. Inline resolution after the gate is the smallest correct fix (plain `if … raise` precedes the calls; no dependency-ordering reliance).
- **Defect 2:** `_select()` iterated all vector-index candidates regardless of type. The authoritative-object type check (`ObjectType.DOCUMENT`) excludes non-documents before result construction; the source document-type check is placed after READ to avoid leaking the type of an unauthorized object.

## Not changed
`/search` route + response contract · AI Core authority · transport ownership · embedder/vector abstractions · permission filtering doctrine · architecture guardrails.

## Verification
- Backend: **1534 passed, 2 skipped** (+7 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean on changed files
