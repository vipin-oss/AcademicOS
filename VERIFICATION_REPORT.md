# FINAL FULL-SYSTEM PRODUCTION AUDIT — AcademicOS (M11 → M13.3.1)

**Audited state:** `feature/m11-ai-workspace` @ `efbf0c6` (pre-remediation) → remediated @ `039b8c1`
**Date:** 2026-08-08 · **Method:** code inspection + runtime reproduction + architecture analysis + repo hygiene + security analysis (prior reports/changelogs NOT trusted)

> **Source-of-truth note:** GitHub origin is stuck at `0afde47` (M11.3.1) due to the documented fetch access-rights failure. The local `feature/m11-ai-workspace` HEAD is the authoritative complete state (all M11→M13.3.1). The audit treats the repository tree itself as truth.

---

## 1. Executive Summary

The M11→M13.3.1 AI stack is architecturally sound and security-correct: single AI Core composition authority, single `Embedder` abstraction, config authority honoured everywhere (no direct `settings` reads in app/api/infra), all AI routes auth-gated, all feature flags wired master-switch-AND-flag, architecture guardrails 16/16, migrations consistent, no accidental persistence in the stateless AI capabilities.

**One production-critical defect** was found and remediated: the **QA route late-gate** (the identical defect fixed for `/ai/related` in M13.3.1, but left unfixed in `/ai/qa` and `/ai/qa/stream`). **One dead directory** (`MigrationFix/`) was removed after proving it is unreferenced. **One pre-existing flaky test** (intake, timing-dependent, unrelated to AI) was identified and explicitly **left untouched** (out of scope; not a product defect).

**Verdict: REQUIRES REMEDIATION → remediation applied → now CLEAN.**

## 2. Production-Critical Defect (remediated)

### QA route resolves AI embedder + vector store before the feature gate
- **Severity:** Production (security/resource). Same class as the M13.3 `/ai/related` defect.
- **Files:** `backend/app/api/routes/ai.py` — `grounded_qa` (`POST /ai/qa`) and `grounded_qa_stream` (`POST /ai/qa/stream`).
- **Behavior (pre-fix):** both declared `vector_repository=Depends(get_vector_repository)` and `embedder=Depends(get_embedder)`. FastAPI resolves all signature dependencies before the handler body, so the feature gate (in the body) ran *after* `get_embedder`/`get_vector_repository` had already executed.
- **Reproduction:** with `AI_QA_ENABLED=false` (default) or `AI_ENABLED=false`, a request to `/ai/qa` still resolved the AI embedder and provisioned/queried the Qdrant collection (verified by the new `TestFeatureGateResolutionOrder` tests, which assert the resolver call log is empty when disabled — it was non-empty pre-fix).
- **Impact:** a disabled capability resolved expensive/external dependencies (AI embedder; vector-store provisioning) — violates the audit's security/resource contract (Part 5/11). Bounded (Qdrant repo is a process singleton), but real.
- **Smallest correct fix (applied):** resolve `embedder = get_embedder(core)` and `vector_repository = get_vector_repository(embedder)` **inline, immediately after the gate**, via the *same* functions `/search` uses. The gate is a plain `if … raise` preceding the calls. Identical to the `/ai/related` fix. The `/search`, `/assistant`, `/intake` routes are always-on with graceful degradation and are correctly **not** changed.
- **Regression tests added:** `TestFeatureGateResolutionOrder` — embedder/vector NOT resolved when `qa=false`, when `AI_ENABLED=false`, and for the stream endpoint; resolved exactly once when enabled.

## 3. Security Findings

| Area | Result |
|---|---|
| Authentication on AI routes | ✅ all use `Depends(get_current_user)`; `/ai/health` intentionally public (liveness, documented) |
| Authorization / READ permission | ✅ summarize/enrich/related enforce READ before loading/embedding; QA inherits from permission-filtered retrieval; related re-authorizes every candidate |
| IDOR / cross-user leakage | ✅ object-level ACL via `PermissionEvaluator` (R4) on source + candidates; stale index rows never leak |
| Prompt injection / untrusted content | ✅ document text delimited (`<<<DOCUMENT>>>`/`<<<SOURCE TEXT>>>`); system instructions treat content as DATA |
| LLM data egress | ✅ no content sent to a provider when AI disabled (gate precedes resolution) |
| Secrets in source | ✅ none (jwt secret default rejected outside dev; API keys read only inside adapters) |
| Disabling AI prevents execution | ✅ verified: master switch off → no embedder/gateway resolution (QA fix closes the last gap) |
| Disabled capabilities & expensive deps | ✅ after fix, every AI route gates before resolving its external dependencies |

## 4. Architecture Findings

- **AI Core = single composition authority.** No route constructs providers/embedders/httpx clients; `build_gateway` is disabled; no bypass constructors referenced in app/api/application. ✅
- **Single `Embedder` abstraction** (`app.application.ports.embedder.Embedder`); two impls (`OpenAIEmbeddingAdapter`, `HashingEmbedder`). No `EmbedderGateway`. ✅
- **Transport ownership:** `OpenAIProvider` is the sole LLM transport owner (httpx isolated — guardrail green). ✅
- **Application layer framework-free** guardrail holds (no pydantic/httpx in `app.application`). ✅
- **16/16 architecture guardrails pass.** No guardrail was weakened across M11→M13.3.1. ✅
- **Provider/model identity, selection, singleton thread-safety, lifespan cleanup** — consistent with M11 freeze.

## 5. Dead / Extra / Obsolete Files

### Removed (proven safe) — `MigrationFix/` (4 files)
- `MigrationFix/backend/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial.py`
- **Evidence unused:** `grep -r MigrationFix` across `*.py/*.md/*.yml/*.ps1/*.sh/*.toml/*.ini/*.cfg` → **zero references** (not in code, tests, scripts, `docker-compose.yml`, or CI). Not the active migration path (`backend/alembic/` is; `env.py` differs). Swept into the M11.1 commit accidentally.
- **Safe to remove:** not imported, not required by tests/runtime/deployment, not a migration artifact (stale duplicate of `0001`), not a compatibility path. ✅ Deleted in the patch.

### Kept (intentional / not proven dead)
- `releases/m13.*/*.zip` + `*.patch` + `VERIFICATION_REPORT.md` — the per-sprint release deliverables the workflow explicitly requires. Kept.
- `academicos-documents-backend.patch`, `academicos-teaching-students.patch` (repo root) — M10-era incremental module release patches, referenced by the M10 `apply_patch.ps1` release workflow. Predate M11; **not proven dead** → kept.
- `FINAL_CERTIFICATE.md`, `FINAL_RELEASE_NOTES.md`, `RELEASE_REPORT.md`, blueprint docs — M10 release artifacts. Kept.

> **Hygiene observation (not a defect):** the repository carries committed binary `.zip` and large `.patch` artifacts. These are intentional release-workflow outputs but inflate the tree. Recommend (out of scope here) moving release binaries to release storage rather than the source tree. Not actioned — would remove deliverables the workflow requires.

## 6. Configuration / Flag Authority Matrix

| Flag / setting | Defined (`config.py`) | `AiConfigView.feature_flags` | Route gate (`core.config`) | Default | Tested |
|---|---|---|---|---|---|
| `AI_ENABLED` | `ai_enabled=True` | `config.enabled` | all AI routes + `get_embedder` | ON | ✅ |
| `AI_SUMMARIZATION_ENABLED` | `ai_summarization_enabled=False` | `summarization` | `/ai/summarize` | OFF | ✅ |
| `AI_SEMANTIC_SEARCH_ENABLED` | `ai_semantic_search_enabled=False` | `semantic_search` | `get_embedder` (`/search`) | OFF | ✅ |
| `AI_QA_ENABLED` | `ai_qa_enabled=False` | `qa` | `/ai/qa`, `/ai/qa/stream` | OFF | ✅ |
| `AI_ENRICHMENT_ENABLED` | `ai_enrichment_enabled=False` | `enrichment` | `/ai/enrich` | OFF | ✅ |
| `AI_RELATED_DOCUMENTS_ENABLED` | `ai_related_documents_enabled=False` | `related_documents` | `/ai/related` | OFF | ✅ |
| `AI_DEFAULT_PROVIDER` / `AI_DEFAULT_MODEL` | defined | consumed by AI Core selection | — | local / "" | ✅ |

- **No direct `settings.ai_*` reads** in `app/api`, `app/application`, `app/infrastructure` (verified by grep). ✅
- Every flag is defined, projected onto the config view, consumed by exactly one gate, and tested (master-switch-off + flag-off). No dead/undefined/orphaned flags. No duplicate sources of truth.

## 7. API Audit
All M12/M13 endpoints: authenticated, authorized, request/response-validated, correct status codes (404 flag, 401 auth, 403 permission, 422 validation, 200 success/fallback), feature-flagged via `core.config`, registered in OpenAPI (269 routes). No misleading success responses (honest `available=False` fallbacks). Backward-compatible (additive fields only).

## 8. Frontend Audit
- `vitest` 70 passed · `tsc --noEmit` exit 0 · `next build` succeeds. Routing, auth, API client, token handling, protected routes compile and unit-test green.
- M11–M13.3.1 made **no frontend changes** (backend-only); no contract mismatch introduced. The previously-observed "dashboard null" symptom is **not reproducible** at type/build/unit-test level. **Environment limitation:** live browser UI integration testing was not possible in this sandbox; the runtime contract is verified via types + build + unit tests, not a live session.

## 9. Database / Storage Audit
8 migrations (`0001`→`0008`, head `0008_document_annotations`) ↔ 8 models — consistent. No M12/M13 feature introduced persistence (all stateless, as designed). Alembic head matches models; no missing/orphaned/destructive migrations. Qdrant is a derived projection (never source of truth). ✅

## 10. Test Quality Audit
- Tests prove contracts (not just counts): strict schema validation, streaming-leak non-resolution, grounding (source text reaches prompt via annotation-service mock — not masked), permission filtering with real `ObjectPermissionEvaluator` + ACL-restricted objects, feature-flag/master-switch negative tests, malformed-LLM-output rejection.
- **No test found to mock away a defect.** The QA grounding test mocks retrieval but asserts source text reaches the prompt via the (mocked) text source — legitimate.
- **Pre-existing flaky test (NOT remediated — out of scope):** `test_intake_api.py::test_pause_resume_completes_exactly_all_items` — timing-dependent polling (~54–64s); fails intermittently under load, passes in isolation/cleaner runs. It is in the **intake** module (pre-M11, unrelated to AI), is an environment/timing flakiness (not a product defect), and hardening it would change unrelated code. **Recommendation:** make it deterministic in a separate follow-up.

## 11. Performance / Lifecycle Audit
- httpx clients: one owned client per `OpenAIProvider` (lazy, reused, `close()` on shutdown); AI Core owns gateway lifecycle; FastAPI lifespan calls `reset_ai_core_cache()`. ✅
- Embedding/vector clients: process-lifetime singletons (Qdrant). ✅
- **Expensive resolution while disabled:** resolved by the QA + related late-gate fixes (the only two feature-gated routes that resolved embedder/vector). ✅
- No unbounded retries (`RETRY_ATTEMPTS=3`), timeouts configured, no duplicate embedding calls (related embeds source text once). ✅

## 12. Repository Integrity
- Clean working tree; branch `feature/m11-ai-workspace`; HEAD `039b8c1` (post-remediation). No accidental local artifacts (`.venv`, `node_modules`, `*.db` gitignored). 1183 tracked files after `MigrationFix/` removal.
- Changelog/manifest/verification reports consistent with the committed state.

## 13. Independent Verification Results (executed)
- **Architecture guardrails:** `16 passed` ✅
- **Full backend (pre-remediation baseline):** 1533 passed, 1 failed (flaky intake test), 2 skipped — the failure is the timing-dependent intake test (passes in isolation), not an AI/product defect.
- **Full backend (post-remediation):** `1538 passed, 2 skipped, 0 failed` (+4 QA regression tests; flaky intake test passed this run).
- **Frontend:** `vitest 70 passed` · `tsc --noEmit exit 0` · `next build` success.
- **Lint:** 0 non-`B008`/`E402` errors on changed files (accepted FastAPI/importskip idioms).

## 14. Remediation Patch (applied)
- **Patch ZIP:** `releases/audit-remediation/audit-remediation-patch.zip` · diff `audit-remediation.patch` (vs `efbf0c6`)
- **Commit:** `039b8c1 fix(audit): QA late-gate …; remove dead MigrationFix`
- **Changed:** `backend/app/api/routes/ai.py` (QA inline resolution, both endpoints), `backend/app/tests/integration/test_ai_qa_api.py` (+4 regression tests).
- **Deleted:** `MigrationFix/` (4 files — proven orphaned; justification above).
- **Tests added:** 4 (`TestFeatureGateResolutionOrder`).
- **Verification:** backend 1538 passed / 2 skipped / 0 failed; architecture 16/16; frontend 70 + tsc clean.

## 15. Final Verdict

**FULL SYSTEM AUDIT: CLEAN** (after remediation).

The one production-critical defect (QA late-gate) is fixed and regression-tested; the one dead directory is removed with proof; the one flaky test is documented and deliberately left for a separate, scoped follow-up (it is not a product defect and is outside the AI scope). No new features introduced; no architecture changed; no working code redesigned.

**M13 is ready for freeze**, subject to a fresh independent confirmation run of the remediation commit `039b8c1`.
