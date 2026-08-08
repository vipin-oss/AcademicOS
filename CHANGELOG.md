# AcademicOS — Sprint M13.3 Changelog (Provenance Retrofit + Related Documents)

Release: **M13.3** · Baseline `0d93094` (M13.2.1) · Commit `97da723` · Date: 2026-08-08
Status: **final M13 sprint — two Blueprint capabilities. Reuse-only: no new retrieval/embedding/vector/provider/transport/AI Core/prompt framework, no persistence, no RAG/agents/memory.**

## Part A — M12.1 summarization provenance retrofit

`SummarizeResult` now carries the M13.1 provenance contract (`provider_id`, `model`, `prompt_id`, `prompt_version`, `input_tokens`, `output_tokens`, `token_usage_estimated`, `latency_ms`), sourced from the actual `GenerationResult` — never fabricated. The summarization prompt identity (`ai.summarize` v1) is recorded on both success and fallback paths; the fallback claims no provider/model (internally consistent). The summarization safety contract (master switch, flag, READ, extracted text, 12k truncation, truncation disclosure, untrusted delimiters, honest fallback, non-persistent) is **unchanged**.

## Part B — `GET /api/v1/ai/related` (semantic related documents)

Documents semantically related to a source, reusing the existing infrastructure end-to-end:

| Reused component | How |
|---|---|
| `AiCore.embedder()` / `Embedder` port | Resolved via the **same** `get_embedder` dependency the `/search` route uses → identical embedder identity + M12 collection dimensions. No second embedding abstraction. |
| `VectorRepository.search` | Existing nearest-neighbour (cosine) behaviour + deterministic ordering. No new vector pipeline/client. |
| `DocumentAnnotationService.extracted_text` | Existing intake source-text pipeline (same as summarize/enrich). |
| `PermissionEvaluator` (R4 gate) | READ on the source before embedding its text; every result re-authorized against the authoritative object. |
| Search scoring | Existing reciprocal-rank-fusion convention reused for the deterministic score (no new ranking algorithm). |

**Contract:** source is permission-checked before its text is embedded; results are READ-filtered; the source is excluded from its own results; `limit` is bounded (`[1, 50]`, invalid → 422); zero results is valid; embedding/vector failures degrade honestly to empty results; no LLM provenance fabricated. New `RelatedDocumentItem` / `RelatedDocumentsResult` DTOs carry only fields already in the search result contract (`object_id`, `object_type`, `title`, `score`, `version`).

**Feature flag:** `AI_RELATED_DOCUMENTS_ENABLED` (default **OFF**), gated exclusively via `core.config.enabled AND feature_flags["related_documents"]` — settings is never read directly. `AI_ENABLED=false` (+ flag on) and flag off both disable the feature with **no embedding call**.

## Files changed
| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | Provenance fields on `SummarizeResult`; new `RelatedDocumentItem`, `RelatedDocumentsResult`, `related_documents_result_dict`. |
| `backend/app/application/use_cases/ai/summarize_document.py` | Populate provenance (success + fallback); prompt identity constants. |
| `backend/app/application/use_cases/ai/related_documents.py` | **new** — `RelatedDocumentsUseCase`. |
| `backend/app/api/routes/ai.py` | `SummarizeResponseModel` provenance fields; `GET /ai/related` + response models. |
| `backend/app/core/config.py` | `ai_related_documents_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"related_documents"` feature flag. |
| `backend/app/tests/unit/test_summarize_document.py` | +3 provenance tests. |
| `backend/app/tests/unit/test_related_documents.py` | **new** — 16 unit tests. |
| `backend/app/tests/integration/test_ai_related_api.py` | **new** — 8 integration tests. |
| `backend/app/tests/unit/test_ai_config_view.py` | flag in expected dict. |

## Verification
- Backend: **1527 passed, 2 skipped** (1500 → 1527; +27 new; zero failures)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean (backend-only)
- Architecture guardrails: **16/16** · ruff clean on changed files (route: accepted `B008`; integration: accepted `E402`)
- App boots, 269 routes (`/ai/related` registered)

---

# AcademicOS — Sprint M13.2.1 Changelog (Corrective — Structured-Output Contract Hardening)

Release: **M13.2.1** · Baseline `0377aec` (M13.2) · Commit `fc40127` · Date: 2026-08-08
Status: **corrective sprint only — two production-critical M13.2 audit defects. No new features, no gateway change, no new abstraction, no new dependency.**

## Defects fixed

| # | Defect | Fix |
|---|---|---|
| 1 | `StructuredGenerationPrompt.schema` was ignored beyond "is the top-level value a dict" — the supplied JSON Schema was never enforced | `_ENRICHMENT_SCHEMA` is now the **single source of truth**: the same schema asserted to the model (`StructuredGenerationPrompt.schema`) is used to validate `structured_generate()` output. No second schema. Validation is enrichment-specific (immediately after `structured_generate()`) so the frozen M11 transport owner (`OpenAIProvider`) stays untouched — zero regression risk for the shared structured-generation contract. |
| 2 | `_coerce()` converted invalid provider output (`123→"123"`, `tags="physics"→("physics",)`, `None→""`, extra fields ignored) into apparently-valid enrichment with `available=True` | The permissive `_coerce()` is **removed**. The gateway's JSON object is now **strictly validated** against the enrichment contract (stdlib-only `_validate_against_schema`, driven by the schema). Missing required fields, `null`, wrong scalar types, scalar-for-array, non-string array items, and unexpected fields (`additionalProperties: false`) are all **rejected**. Invalid output returns the honest `available=False` fallback and never reaches the successful-response path. |

## Exact validation mechanism
- **Stdlib-only**, schema-driven (`isinstance` checks over the JSON-Schema *subset* the enrichment schema uses: `type`, `required`, `properties`, `items.type`, `additionalProperties`).
- `pydantic` is **not** used in `app.application` — the M11 architecture guardrail (`test_application_depends_only_on_domain_and_stdlib`) forbids framework imports there. `jsonschema` is not a dependency. A focused stdlib validator is therefore the smallest correct, safe implementation.
- The `OpenAIProvider` gateway / `structured_generate()` is **unchanged**.

## Required enrichment contract (now enforced, not coerced)
`title`, `summary`: required `string` · `tags`, `categories`, `keywords`: required `array` of `string` · extra fields: **rejected** (`additionalProperties: false`).

## Files changed
| Path | Change |
|---|---|
| `backend/app/application/use_cases/ai/enrich_document.py` | Replaced permissive `_coerce()` with strict `_validate_against_schema()`; `_ENRICHMENT_SCHEMA` gains `additionalProperties: false` and becomes the single source of truth; invalid output → `available=False` fallback. |
| `backend/app/tests/unit/test_enrich_document.py` | Permissive-coercion tests changed to assert **rejection**; full 21-point audit regression matrix added (#1–#19 use-case level). |

## Verification
- Backend: **1500 passed, 2 skipped** (1484 → 1500; +net regression coverage; zero failures)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean (unaffected — backend-only)
- Architecture guardrails: **16/16** (incl. the application framework-free guardrail) · ruff clean
- Shared structured-generation tests (openai hardening / placeholders / dtos): all green (gateway unchanged)

---

# AcademicOS — Sprint M13.2 Changelog (Document Enrichment)

Release: **M13.2** · Baseline `96599be` (M13.1.1) · Commit `b52f7f0` · Date: 2026-08-08
Status: **first production use of structured generation — document enrichment. No new retrieval/persistence/embedding/search/transport/provider/AI Core/prompt framework.**

## What was built

`POST /api/v1/ai/enrich` extracts production-useful metadata (title, summary, tags, categories, keywords) from a document's authoritative extracted text via the AI Core's `LanguageModelGateway.structured_generate()` (the M11.3 capability activated for the first time), returning a validated structured object plus the M13.1 provenance contract.

| Component | Detail |
|---|---|
| `POST /api/v1/ai/enrich` | On-demand document enrichment, feature-flagged (`AI_ENRICHMENT_ENABLED`, default off). READ permission + extracted-text required. |
| `EnrichDocumentUseCase` | Mirrors the summarization safety contract but routes through `structured_generate()`. Coerces + validates the model JSON to the enrichment shape. |
| `EnrichmentResult` DTO | title, summary, tags, categories, keywords, available, truncation disclosure + **provenance** (provider_id, model, prompt_id/version, tokens, latency). |
| Structured validation | Missing/extra/wrong-type JSON fields degrade to honest defaults — never crash. |
| Feature flag | `AI_ENRICHMENT_ENABLED` (default off); routed exclusively through `AiCore.config` (master switch AND feature flag). |

## Reused components (no new abstractions)
`AiCore`, `LanguageModelGateway.structured_generate()`, `DocumentAnnotationService` + `GetIntakeExtractedTextUseCase` (intake pipeline), `PermissionEvaluator` (READ), the existing document-loading + extracted-text pipeline, existing DTO patterns (`StructuredGenerationPrompt`/`StructuredGenerationResult`), existing error handling (404/403/422), existing permission handling, existing AI fallback behaviour. AI Core authority, transport ownership and all 16 architecture guardrails unchanged.

## What did NOT change
No new retrieval pipeline · no new persistence model · no new embedding system · no new search implementation · no new transport owner · no new provider abstraction · no new AI Core · no new prompt framework. The frontend is untouched (backend-only, additive endpoint + additive flag).

## Verification
- Backend: **1484 passed, 2 skipped** (+22 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean (unaffected)
- Architecture guardrails: **16/16** · ruff clean on changed files (route carries only the pre-existing FastAPI `B008` idiom)

---

# AcademicOS — Sprint M13.1.1 Changelog (Corrective — QA Defect Fixes)

Release: **M13.1.1** · Baseline `4f079a8` (M13.1) · Commit `ae55aeb` · Date: 2026-08-08
Status: **corrective sprint only — three production-critical QA defects fixed. No new features, no new abstractions, no persistence, no redesign.**

## Defects fixed

| # | Defect | Fix |
|---|---|---|
| 1 | Streaming QA leaked partial answers (tokens emitted immediately; a later gateway failure returned `available=false` but tokens had already leaked; a stream ending without a completion event returned the accumulated partial answer as `available=true`) | Token deltas are now **buffered and flushed ONLY after a confirmed completion event**. A gateway failure or a stream that ends without a completion event is a **generation failure** — buffered tokens are discarded and the honest `available=false` fallback is yielded, the same honesty contract as synchronous QA. No token event is emitted until success is confirmed. |
| 2 | QA was not grounded — the prompt carried only `RetrievedItem` metadata (title, id, version, source, score); no document content reached the model | The **authoritative document text** for each retrieved item is now loaded from the existing intake-extraction pipeline (`DocumentAnnotationService.extracted_text` — the same source the document viewer and summarization use) and injected into the prompt as delimited untrusted data, so the model answers from evidence rather than document titles. No new retrieval pipeline; no duplicated `AssistantContextBuilder`. |
| 3 | Provenance reported the wrong prompt identity — `prompt_id` was hardcoded to `ai.grounded_qa` while the generated prompt is `assistant.default` | Provenance now reports the **`prompt_id` / `prompt_version` actually produced by the prompt builder** (`assistant.default`), consistently across sync, streaming, success and fallback paths. The hardcoded identity constants are removed. |

A latent bug was also fixed: `execute()` called `_verify_citations()` twice.

## Files changed

| Path | Change |
|---|---|
| `backend/app/application/use_cases/ai/grounded_qa.py` | Leak-proof streaming (buffer + flush-on-completion + generation-failure fallback); authoritative source-text injection via `DocumentAnnotationService`; prompt-builder-driven provenance; shared `_success_result` / `_fallback` helpers. |
| `backend/app/api/routes/ai.py` | Both QA endpoints wire the annotation service + storage so QA is grounded in production. |
| `backend/app/tests/unit/test_grounded_qa.py` | **new** — 13 regression tests (4 streaming-leak, 5 grounding, 4 provenance). |

## Reused components (no new abstractions)
`DocumentAnnotationService` + `GetIntakeExtractedTextUseCase` (intake pipeline), `AssistantRetrievalService`, `AssistantContextBuilder`, `AssistantPromptBuilder`, `CitationBuilder`, `AnswerVerifier`, `LanguageModelGateway.generate/stream()`, `AiCore`, `PermissionEvaluator`. AI Core authority, transport ownership and all 16 architecture guardrails are unchanged.

## Verification
- Backend: **1462 passed, 2 skipped** (+13 new regression; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean (unaffected — backend-only, unchanged response shape)
- Architecture guardrails: **16/16** · ruff clean on changed files

---

# AcademicOS — Sprint M13.1 Changelog (Grounded Question Answering)

Release: **M13.1** · Baseline `0a0c0c7` (M12.3.1) · Date: 2026-08-08
Status: **flagship AI feature — grounded QA with citations + provenance.**

## What was built

| Component | Detail |
|---|---|
| `POST /ai/qa` | Stateless grounded QA: retrieve → context → prompt → generate → verify → return with citations. |
| `POST /ai/qa/stream` | SSE streaming variant: token events → completion event with verified answer + provenance. |
| `GroundedQAUseCase` | Composes existing retrieval/context/citation/prompt/verification pipeline — zero duplication. |
| `QAResult` DTO | answer, available, citations, retrieved_count, truncated + **provenance** (provider_id, model, prompt_id/version, tokens, latency). |
| Provenance contract | Defined in M13.1; all gateway metadata surfaced in the response. |

## Reused components (no modifications)
`AssistantRetrievalService`, `AssistantContextBuilder`, `CitationBuilder`, `AssistantPromptBuilder`, `AnswerVerifier`, `LanguageModelGateway.generate/stream()`, `PermissionEvaluator`.

## Guardrail update
AI use cases (`application/use_cases/ai/`) may import from `application/assistant/` (compose existing services). Only the AI Core (`application/ai/`) stays pure.

## Verification
- Backend: **1444 passed, 2 skipped** (+5 new integration; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean · app boots (267 routes)

---

# AcademicOS — Sprint M12.3.1 Changelog (Semantic Search Configuration Authority Fix)

Release: **M12.3.1** · Baseline `f0238c6` (M12.3) · Date: 2026-08-08

## Fix

The search route's `get_embedder()` read `settings.ai_semantic_search_enabled` directly, bypassing the `AI_ENABLED` master switch. Now checks `ai_core.config.enabled` (master) AND `ai_core.config.feature_flags["semantic_search"]` — single source of truth.

## Regression tests
- `AI_ENABLED=false` blocks semantic embedding even when flag is on.
- No AI embedder resolution occurs when master switch is off.
- Existing flag on/off behaviour unchanged.

## Verification
- Backend: **1444 passed, 2 skipped** (+3 new; zero regressions); 16/16 guardrails; ruff clean.

---

# AcademicOS — Sprint M12.3 Changelog (Semantic Search Activation)

Release: **M12.3** · Baseline `70500b6` (M12.2.1) · Date: 2026-08-08
Status: **semantic search activated via existing /search — no new endpoint, no new abstractions.**

## What was built

The existing `GET /search` endpoint now automatically uses the AI Core's real embedder when `AI_SEMANTIC_SEARCH_ENABLED` is on, and the deterministic `HashingEmbedder` when off. No duplicate API; the response shape is unchanged.

| Change | Detail |
|---|---|
| `get_embedder()` | Resolves AI Core embedder when flag on; `HashingEmbedder` when off. |
| `get_vector_repository()` | Uses the SAME resolved embedder for Qdrant collection dimensions (one identity everywhere). |
| `AI_SEMANTIC_SEARCH_ENABLED` | New config flag (default `false`); `AiConfigView.semantic_search` feature flag. |
| Graceful degradation | AI Core embedder unavailable → `HashingEmbedder` (search never breaks). |

## Verification
- Backend: **1441 passed, 2 skipped** (+4 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean

---

# AcademicOS — Sprint M12.2.1 Changelog (Embedding Contract Hardening)

Release: **M12.2.1** · Baseline `8ef3ac2` (M12.2) · Date: 2026-08-08

## Fixes

| # | Defect | Fix |
|---|---|---|
| 1 | `embed()` returned vectors without validating length vs configured dimensions | `_validate_dimensions()` checks `len(vector) == embedding_dimensions`; raises `_EmbeddingError` on mismatch — never returns an invalid vector. |
| 2 | `build_ai_core` constructed a real adapter with missing/zero/negative dimensions | Now requires `embedding_model` AND `embedding_dimensions > 0` AND `base_url`; otherwise falls back to `HashingEmbedder`. |

## Verification
- Backend: **1437 passed, 2 skipped** (+7 new; zero regressions); 16/16 guardrails; ruff clean.

---

# AcademicOS — Sprint M12.2 Changelog (Embedding Capability)

Release: **M12.2** · Baseline `980a77b` (M12.1.1) · Date: 2026-08-08
Status: **embedding integration on the frozen M11 AI Core. No semantic search, no RAG.**

## What was built

| Component | Detail |
|---|---|
| `OpenAIEmbeddingAdapter` | Implements the **existing** `Embedder` port (`application/ports/embedder.py`). Calls `/v1/embeddings` via httpx; same retry/error doctrine as `OpenAIProvider`; lazy owned client + `close()`. |
| `AiCore.embedder()` | The AI Core resolves the embedder: real adapter when an embedding-capable provider is configured, `HashingEmbedder` fallback otherwise. |
| `build_ai_core` composition | Finds the first provider with `embedding_model` + `base_url`; builds `OpenAIEmbeddingAdapter`; else `HashingEmbedder`. |
| `ProviderConfig` | Gains `embedding_model` + `embedding_dimensions` (parsed from `AI_PROVIDERS_JSON`). |
| Guardrails | `provider_factory` exempt from ALL infra imports (composes gen + embed); two transport owners (gen + embed). |

## Design decision (finalized blueprint)

The finalized M12 blueprint (post-Chrome-review) specifies **reusing the existing `Embedder` port** — not creating a sibling `EmbedderGateway`. This avoids duplicate abstraction and lets `SearchObjectsUseCase` and `SearchIndexApplier` use one consistent embedding identity.

## Verification
- Backend: **1430 passed, 2 skipped** (+14 new; zero regressions)
- Architecture guardrails: **16/16**
- ruff clean; app boots (265 routes)

---

# AcademicOS — Sprint M12.1.1 Changelog (Configuration Authority Fix)

Release: **M12.1.1** · Baseline `8232ee0` (M12.1) · Date: 2026-08-08
Status: **corrective fix — AI_ENABLED master switch now gates summarization.**

## Fix

The summarization route (`POST /ai/summarize`) read `settings.ai_summarization_enabled` directly, bypassing the `AI_ENABLED` master switch. When `AI_ENABLED=false` but `AI_SUMMARIZATION_ENABLED=true`, document content could reach a provider. Now the route checks the AI Core config (`core.config.enabled` AND `core.config.feature_flags["summarization"]`) — the single source of truth. No `settings` import remains.

## Regression tests
- `AI_ENABLED=false` blocks summarization even when `AI_SUMMARIZATION_ENABLED=true` (404).
- No `gateway.generate()` invocation occurs when AI is disabled.
- `AI_ENABLED=true` + flag on proceeds normally.

## Verification
- Backend: **1416 passed, 2 skipped** (+3 new; zero regressions); 16/16 guardrails; ruff clean.

---

# AcademicOS — Sprint M12.1 Changelog (Document Summarization)

Release: **M12.1** · Baseline `e33246d` (M11.3.4 frozen) · Branch `feature/m11-ai-workspace` · Date: 2026-08-08
Status: **first user-facing AI capability on the M11 AI Core. No embedding work, no semantic search, no RAG.**

## What was built

| Component | Detail |
|---|---|
| `POST /api/v1/ai/summarize` | On-demand document summarization, feature-flagged (`AI_SUMMARIZATION_ENABLED`, default off). |
| `SummarizeDocumentUseCase` | Orchestrates: permission check → extracted text → truncation → safe prompt → `generate()` → result. |
| `SummarizeResult` DTO | `summary`, `available`, `truncated`, `chars_used`, `chars_total`. |
| `PermissionDeniedError` | Application-layer 403 error (new). |
| Safety contract | READ permission enforced; untrusted-content delimiters; truncation disclosed; honest fallback. |

## Verification

- Backend: **1413 passed, 2 skipped** (+13 new; zero regressions)
- Architecture guardrails: **16/16**
- `ruff --select F401,I001` clean; app boots (265 routes)

---

# AcademicOS — Sprint M11.3.4 Changelog (Final Production Runtime Contract Fixes)

Release: **M11.3.4** · Baseline `72248be` (M11.3.3) · Branch `feature/m11-ai-workspace` · Date: 2026-08-08
Status: **two verified production contract defect fixes — no redesign, no new capabilities. Final M11 freeze sprint.**

## Fixes

| # | Defect | Fix |
|---|---|---|
| 1 | Health status `ok` overclaimed verified reachability for a provider that merely had `base_url` | The strongest honest aggregate status without a live probe is **`configured`** (has endpoint, can attempt) — not `ok`. `HEALTH_OK` is reserved for operationally-verified state (never used without a probe). |
| 2 | `OpenAIProvider.stream()` did not check `streaming_enabled` — streaming bypassed configuration | `stream()` now raises `LlmProviderError` when `streaming_enabled` is False. `build_ai_core` ANDs the global `AI_STREAMING_ENABLED` with per-provider `streaming_enabled`, so global-off disables all providers. `generate()` is unaffected. |

## Verification

- Backend: **1400 passed, 2 skipped** (+6 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16**
- `ruff --select F401,I001` clean

---

# AcademicOS — Sprint M11.3.3 Changelog (Final Runtime Hardening)

Release: **M11.3.3** · Baseline `f8d7b2e` (M11.3.2) · Branch `feature/m11-ai-workspace` · Date: 2026-08-08
Status: **final runtime hardening — no architecture redesign, no new capabilities. M11 freeze-ready.**

Closes the last verified production runtime findings. Non-executable providers
cannot become runtime primaries; the AI Core lifecycle is wired into the FastAPI
shutdown; and the singleton is thread-safe.

## Fixes

| # | Finding | Fix |
|---|---|---|
| 1 | Assistant readiness used `.configured` (declared), not `.executable` (can run) | `_gateway_ready` now checks `.executable`; a declared-but-non-executable provider degrades to rules — never becomes the primary. |
| 2 | No graceful shutdown for AI Core resources | A FastAPI `lifespan` handler calls `reset_ai_core_cache()` on shutdown, closing owned httpx clients exactly once. |
| 3 | Singleton initialization not thread-safe | Double-checked locking (`threading.Lock`) on `get_ai_core`; `reset_ai_core_cache` is locked and idempotent. |
| 4 | Runtime guardrails | 7 new behaviour tests: non-executable never primary, lifecycle shutdown, singleton concurrency, idempotent reset. |

## Verification

- Backend: **1392 passed, 2 skipped** (+7 new; 2 pre-existing flaky productivity tests pass in isolation)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16**
- `ruff --select F401,I001` clean; app boots with lifespan (264 routes)

---

# AcademicOS — Sprint M11.3.2 Changelog (Final Production Contract Hardening)

Release: **M11.3.2** · Baseline `0afde47` (M11.3.1) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **production-contract hardening only — no architecture redesign, no new capabilities. Final hardening before M11 freeze.**

Closes the remaining production-contract / operational findings of the hostile
audit. Runtime identity is fully consistent across the public APIs, health
separates configured/executable/operational, and the AI Core owns the gateway
lifecycle.

## Fixes

| # | Finding | Fix |
|---|---|---|
| 1, 5 | Runtime identity disagreement (`/ai/models` used the raw config default) | `model_records` now uses the **runtime-effective** default (same source as `health_summary`); `/ai/health` and `/ai/models` never disagree on provider/model. |
| 2 | Health conflated configured/executable/operational | `ProviderHealth`/`ProviderRecord` distinguish **configured** (declared), **executable** (can run) and **operational** (None — no live probe). `status` "ok" / `default_provider_valid` require EXECUTABLE, never mere config. |
| 3 | Compatibility seam | Legacy test-injection ctor + `build_gateway_from_params` deprecated + isolated (architecture guardrail; production never imports them). |
| 4 | Gateway lifecycle not owned | `AiCore.close()` owns gateway cleanup; `get_ai_core` is a lazy singleton so httpx clients are reused (one consistent lifecycle), not leaked per request. No shutdown manager (by design). |
| 6 | Runtime contract tests | +8 tests: health/models agreement, three-state health, lifecycle ownership. |
| 7 | Documentation | README + developer guide corrected to match the implementation; no over-claimed capabilities. |

## Verification

- Backend: **1387 passed, 2 skipped** (zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16**
- `ruff check --select F401,I001` clean; app boots (264 routes)

---

# AcademicOS — Sprint M11.3.1 Changelog (Production Correctness Hardening)

Release: **M11.3.1** · Baseline `e7c1d8e` (M11.3) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **correctness fixes only — no architecture redesign, no new capabilities, no new SDKs.**

Resolves the production-correctness / runtime-semantics findings of the
hostile audit of M11.3. The AI Core is internally consistent: provider
identity is unambiguous, model selection is correct, `AI_DEFAULT_MODEL` matches
runtime, and health reflects actual executability.

## Fixes

| Audit finding | Fix |
|---|---|
| #1 Provider/model/kind contract ambiguity | `provider_id` is the configured catalogue identity (a gateway property), DISTINCT from `kind`; the assistant selects by `provider_id` (`model_id` kept as a deprecated alias resolved in `__post_init__`); the conversation pin is stored under `assistant.provider_id` (legacy `assistant.model_id` still read). |
| #2 `AI_DEFAULT_MODEL` ignored at runtime | `_resolve_default_provider_id` now honours `AI_DEFAULT_MODEL` (the provider whose model matches becomes the default); `AI_DEFAULT_PROVIDER` takes precedence over the legacy setting. Health surfaces the effective default model. |
| #3 Provider identity inconsistency | Health rows are keyed by `provider_id` (one row per provider); `ProviderHealth.provider_id` == `ModelInfo.provider_id`; multiple providers of the same kind are distinguishable. |
| #4 Misleading health | `/ai/health` reports the EFFECTIVE default provider; `default_provider_valid` is True only when the default is actually executable; `status` is never `ok` when the selected provider cannot run. |
| #5 Compatibility bypass | `AiCore.build_gateway` is disabled (gateways come only from the catalogue). New guardrail: `api/` and `application/` never import the bypass constructors (`LlmAssistantProvider`, `build_gateway_from_params`). |
| #6 Semantic guardrails | New `test_production_provider_isolation` + `test_ai_runtime_contract` (runtime: identity, multi-provider distinguishability, selection precedence, `AI_DEFAULT_MODEL` influence, health/runtime consistency). |
| #7 Documentation | Developer guide + `config.py` comments corrected to match the implementation; no over-claimed capabilities. |

## What did NOT change

- No architecture redesign; no new AI capabilities / SDKs; `RuleBasedAssistantProvider` / `FallbackAssistantProvider` untouched.
- API surface additions are backward-compatible (`provider_id` added; `model_id` retained as alias; legacy conversations still resolve).

## Verification

- Backend: **1379 passed, 2 skipped** (zero regressions; +13 new tests)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16**
- `ruff check --select F401,I001` clean; app boots (264 routes)

---

# AcademicOS — Sprint M11.3 Changelog (AI Core Configuration Authority & OpenAI Hardening)

Release: **M11.3** · Baseline `01a9f04` (M11.2.1) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **AI Core is the single production authority; OpenAI adapter production-ready. No RAG/embeddings/memory/agents/chat-UI.**

After M11.3 there is exactly one production authority for provider, model,
credentials and runtime execution: the AI Core. The assistant no longer
constructs a `ProviderConfig` anywhere, and the OpenAI transport is
production-grade.

## Configuration & selection authority (items 1, 2, 5)

| Change | Detail |
|---|---|
| Provider-id-keyed catalogue | `AiCore` holds providers by id (multiple per kind), with `select_provider(requested, pinned)` (override > pin > default) and `gateway(provider_id)`. The health surface still projects the 5 discovery kinds - the `/ai/*` API shape is unchanged. |
| Authoritative config | `build_ai_core` builds the catalogue from `AI_PROVIDERS_JSON`. When empty, it DEPRECATED-synthesizes providers from legacy `ASSISTANT_*` settings, so existing deployments keep working unchanged. |
| Assistant consumes AI Core | The ask use case resolves providers through `AiCore` (no `ProviderConfig`, no provider construction). `build_assistant_provider` composes the translator over an AI-Core gateway + rules fallback. |
| Legacy retired from production | `ModelRegistry` / `registry_from_settings` are deprecated + isolated (kept for their unit tests). The legacy `build_provider` (which built `ProviderConfig` outside the AI Core) is removed. |
| Config-authority guardrail | New `test_ai_config_authority`: `ProviderConfig(...)` may be constructed ONLY inside the AI Core. |

## OpenAI adapter hardening (item 3)

| Concern | Fix |
|---|---|
| Client lifecycle / reuse | One owned `httpx.Client` per adapter (lazy, cached, reused); `close()` releases it; injected clients are not closed. |
| Generation policy | `max_tokens` + `temperature` honoured from `ProviderConfig` (per-prompt overrides); defaults preserve determinism (T=0). |
| Honest accounting | `finish_reason` and token `usage` parsed when the endpoint reports them (`estimated=False`); deterministic estimate otherwise; `latency_ms` measured; streaming requests `stream_options.include_usage`. |
| Structured output | `structured_generate` implemented (JSON-object mode) - a REAL capability. Capabilities report only what is implemented (`chat`, `stream`, `structured_output`); the unimplemented `tools` is no longer claimed. |

## Health reporting (item 4)

Per-provider `configured` status is `base_url`-based: a declared model without
a `base_url` reports `not_configured` (no misleading "healthy" state).

## What did NOT change

- **`RuleBasedAssistantProvider` / `FallbackAssistantProvider`** untouched (P9).
- **API surface**: `/ai/health`, `/ai/providers`, `/ai/models`, `/assistant/*` shapes unchanged.
- **No new dependencies / SDKs / migrations / settings required.**
- Not implemented (out of scope): RAG, embeddings, memory, agents, chat UI.

## Verification

- Backend: **1366 passed, 2 skipped** (zero regressions)
- Frontend: **70 vitest passed (15 files)** · `tsc --noEmit` clean
- Architecture guardrails: **15/15**
- `ruff check --select F401,I001` clean on changed files; app boots (264 routes)

---

# AcademicOS — Sprint M11.2.1 Changelog (Architecture Hardening — ADR-001)

Release: **M11.2.1** · Baseline `1c1d81f` (M11.2) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **architecture hardening only — no behaviour change, no new providers, no SDKs**

An independent hostile audit of M11.2 found that ADR-001 was only partially
implemented: the assistant still constructed the concrete `OpenAIProvider`
directly (in `build_provider` and `LlmAssistantProvider`'s legacy constructor),
so gateway creation was **not** owned by AI Core, there were effectively two
composition roots, and the only guardrail checked httpx imports. M11.2.1 makes
ADR-001 fully true and machine-enforced.

## What changed

| Audit finding | Fix |
|---|---|
| AI Core bypass (features construct concrete providers) | `build_gateway()` is now **the single gateway constructor** in `infrastructure/ai/provider_factory.py` — the only place a concrete provider is imported or instantiated. The assistant's `build_provider` and `LlmAssistantProvider` obtain gateways through `AiCore.build_gateway` / `build_gateway`; neither imports `OpenAIProvider` anymore. |
| Duplicate transport composition (two roots) | One composition authority: the AI Core. `build_ai_core` builds the catalogue through `build_gateway`; features consume `AiCore.build_gateway`. |
| Weak guardrails (httpx only) | `test_transport_ownership` now spans every feature layer; new `test_ai_composition_authority` forbids any feature from importing a concrete provider and asserts `build_gateway` is defined only in the composition root. |
| DI direction | `get_assistant_provider_factory` is bound to `ai_core`, so per-conversation model selection also flows through the AI Core. `application/ai` still imports nothing from the assistant (existing AI purity guardrail). |

## New surface

- `AiCore.build_gateway(config) -> LanguageModelGateway` — the application-pure
  seam a feature consumes to obtain a transport gateway. Delegates to the
  registry (concrete instantiation stays in the composition root).

## What did NOT change

- **No behaviour change** — full suite green; transport, fallback, streaming,
  citations, model selection, review gate all unchanged.
- **`RuleBasedAssistantProvider` and `FallbackAssistantProvider`** untouched.
- **No new providers / SDKs / functionality.** `AI_*` and `ASSISTANT_*` config
  both remain (compat preserved); retiring `ASSISTANT_*` is still M11.3.
- The `AssistantProvider` port and `ModelRegistry` remain as transient seams.

## Files modified

`backend/app/infrastructure/ai/provider_factory.py` (single constructor + re-exports) ·
`backend/app/application/ai/core.py` (`build_gateway` seam) ·
`backend/app/infrastructure/assistant/provider_factory.py` (consumes AI Core) ·
`backend/app/infrastructure/llm/llm_provider.py` (consumes AI Core) ·
`backend/app/api/routes/assistant.py` (factory bound to `ai_core`)

## Files added / strengthened

`backend/app/tests/architecture/test_ai_composition_authority.py` (new — 2 guardrails) ·
`backend/app/tests/architecture/test_transport_ownership.py` (broadened to all feature layers)

## Verification

- Backend suite: **1354 passed, 2 skipped** (M11.2 baseline 1352 + 2 new composition guardrails; **zero regressions**)
- Architecture guardrails: **14/14** (7 domain + 4 AI + 1 transport + 2 composition)
- Hostile-audit re-check: **no feature imports a concrete provider**; **one module-level `build_gateway`**; **httpx only in `infrastructure/ai/llm/openai.py`**
- `ruff check --select F401,I001` clean on changed files; app boots (264 routes)

---

# AcademicOS — Sprint M11.2 Changelog (Architecture Alignment — ADR-001)

Release: **M11.2** · Baseline `1c0e82e` (M11.1) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **architecture alignment only — no behaviour change, no new providers, no SDKs, no new user-facing functionality**

Sprint M11.2 implements ADR-001: it collapses the duplicate LLM transport
into a single owner. The OpenAI-compatible transport that lived in
`infrastructure/llm/LlmAssistantProvider` is relocated to the AI Core's
`LanguageModelGateway` adapter (`infrastructure/ai/llm/openai.py::OpenAIProvider`),
which becomes the **single** owner of generative-LLM transport. The assistant
now consumes a `LanguageModelGateway` instead of owning transport. The
deterministic rules engine and the fallback chain are untouched.

## What changed

| Concern | Change |
|---|---|
| Singular transport ownership | New `OpenAIProvider` (`infrastructure/ai/llm/openai.py`) owns the OpenAI-compatible httpx transport (relocated verbatim — bounded retries, non-retryable status set, SSE parsing, `LlmProviderError`). It is the only module under `infrastructure/ai` / `infrastructure/llm` that imports httpx. |
| `LanguageModelGateway` = the provider abstraction | `OpenAIProvider` implements the gateway port (generate/stream/structured_generate/health/list_models/count_tokens/estimate_cost). Honest "not configured" surface when no `base_url` is set (parity with the placeholder); real chat-completions when configured. |
| Assistant consumes AiCore | `LlmAssistantProvider` is now a thin translator over a `LanguageModelGateway` (no transport). `build_provider` constructs the `OpenAIProvider` gateway from the model spec and wraps it; the assistant route injects `get_ai_core` for generation defaults. |
| Credential seam (ADR-001 Q7.5) | `ProviderConfig.api_key` — the single secret an adapter may read (inside the adapter only, never logged). `AI_PROVIDERS_JSON` parsing reads it. |
| Provider-independent extension | `GenerationPrompt.extra_body` — an optional dict of extra request fields the gateway merges into its wire body. The assistant attaches its numbered evidence this way, preserving the exact prior wire format without leaking an assistant concept into the gateway. |
| Transport-ownership guardrail | New `tests/architecture/test_transport_ownership.py` fails CI if `infrastructure/llm` ever re-imports httpx — the structural vaccine against the duplicate-transport regression. |

## What did NOT change (the sprint constraints)

- **No behaviour change.** Every transport, pipeline and assistant test
  (unit + integration, including the citations-on-wire contract) passes
  unchanged. The fallback chain, streaming, model selection, review gate
  and the deterministic rules provider are byte-for-byte identical.
- **`RuleBasedAssistantProvider` and `FallbackAssistantProvider`** are
  untouched (the system's P9 "degrade, never disappear" guarantee).
- **No new providers, no SDKs.** `OpenAIProvider` is the *relocated*
  pre-existing transport (it was already `LlmAssistantProvider`), not a new
  integration. httpx was already a dependency. The other four providers
  remain honest placeholders.
- **`AssistantProvider` port and `ModelRegistry`** are intentionally retained
  as transient seams (ADR-001 retires them in M11.3 with config consolidation).

## Files added

`backend/app/infrastructure/ai/llm/openai.py` (real gateway) ·
`backend/app/tests/architecture/test_transport_ownership.py` (guardrail)

## Files modified

`backend/app/application/dtos/ai.py` (`ProviderConfig.api_key`, `GenerationPrompt.extra_body`) ·
`backend/app/application/ai/providers/config.py` (parse `api_key`) ·
`backend/app/infrastructure/ai/llm/placeholders.py` (`OpenAIProvider` moved out; the 4 honest placeholders remain) ·
`backend/app/infrastructure/ai/provider_factory.py` (registers the real `OpenAIProvider`) ·
`backend/app/infrastructure/llm/llm_provider.py` (`LlmAssistantProvider` → thin translator; `LlmProviderError` re-exported) ·
`backend/app/infrastructure/assistant/provider_factory.py` (`build_provider` builds the gateway) ·
`backend/app/api/routes/assistant.py` (`get_assistant_provider` consumes `get_ai_core`) ·
`backend/app/tests/unit/test_ai_placeholders.py` (import `OpenAIProvider` from its new home)

## Verification

- Backend suite: **1352 passed, 2 skipped** (baseline 1351 + 1 new transport-ownership guardrail; **zero regressions**)
- Architecture guardrails: **12/12** (7 domain + 4 AI + 1 transport-ownership)
- `ruff check --select F401,I001` clean on every changed file
- App boots; 264 routes registered; `/api/v1/ai/health` and `/api/v1/assistant/*` unchanged

---

# AcademicOS — Sprint M11.1 Changelog (AI Foundation)

Release: **M11.1** · Baseline `4d3c4cd` (M10 RC1, frozen) · Branch `feature/m11-ai-workspace` · Date: 2026-08-07
Status: **infrastructure only — no chat, no RAG, no memory, no agents, no embeddings, no LLM calls**

Sprint M11.1 builds the AI Core every future AI capability plugs into.
The system's behavior is unchanged: no generation happens anywhere; the
five provider adapters are honest placeholders that report
"Not Configured".

## What was built

| Layer | Deliverable |
|---|---|
| AI application layer | `app/application/ai/` — pure ports + services: `LanguageModelGateway` protocol (health / list_models / generate / stream / structured_generate / count_tokens / estimate_cost), AI DTOs with strict validation + serialization helpers, `ProviderRegistry` (kind → factory discovery), `AI_PROVIDERS_JSON` parsing, `AiConfigView` (defaults, generation knobs, feature flags), `AiCore` facade (health / providers / models aggregation + gateway lookup), domain errors (`AiNotConfiguredError` 503-mapped, `UnknownProviderError`) |
| Use cases | `app/application/use_cases/ai/` — `GetAiHealthUseCase`, `ListAiProvidersUseCase`, `ListAiModelsUseCase` (thin, testable, HTTP-free) |
| Provider placeholders | `app/infrastructure/ai/llm/placeholders.py` — OpenAI, Anthropic, Google, Ollama, Local. All report `not_configured`; generation raises `AiNotConfiguredError` (no fake AI); token/cost estimates are deterministic and real |
| Composition + DI | `app/infrastructure/ai/provider_factory.py` (`build_ai_core`, the single factory) + `app/api/dependencies/ai.py` (`get_ai_core`, test-overridable seam) |
| Health API | `GET /api/v1/ai/health` (public, JSON), `GET /api/v1/ai/providers` + `GET /api/v1/ai/models` (authenticated, JSON) |
| Configuration | `AI_ENABLED`, `AI_DEFAULT_PROVIDER`, `AI_DEFAULT_MODEL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS`, `AI_TIMEOUT_SECONDS`, `AI_STREAMING_ENABLED`, feature flags (`AI_CHAT_ENABLED`, `AI_RAG_ENABLED`, `AI_MEMORY_ENABLED`, `AI_AGENTS_ENABLED`, `AI_DOCUMENT_UNDERSTANDING_ENABLED` — all OFF), `AI_PROVIDERS_JSON` |
| Frontend | `/settings/ai` page (sidebar "AI Settings"): health banner, default provider / current model, capability flags, provider catalogue, model list — read-only, no chat UI |
| Guardrails | 4 new architecture tests: AI application purity, adapter independence, single composition seam, clean imports (7 domain + 4 AI = 11) |
| Docs | `AI_DEVELOPER_GUIDE.md` (how to add a provider), README AI section, this changelog, AI Architecture v1.0 appendix |

## Files added

`backend/app/application/ai/{__init__,errors,config,core}.py` ·
`backend/app/application/ai/llm/{__init__,ports,estimates}.py` ·
`backend/app/application/ai/providers/{__init__,config,registry}.py` ·
`backend/app/application/use_cases/ai/{__init__,get_ai_health,list_ai_providers,list_ai_models}.py` ·
`backend/app/application/dtos/ai.py` ·
`backend/app/infrastructure/ai/{__init__,provider_factory}.py` ·
`backend/app/infrastructure/ai/llm/{__init__,placeholders}.py` ·
`backend/app/api/dependencies/ai.py` · `backend/app/api/routes/ai.py` ·
`backend/app/tests/unit/test_ai_{dtos,estimates,provider_config,registry,config_view,core,placeholders}.py` ·
`backend/app/tests/integration/test_ai_health_api.py` ·
`backend/app/tests/architecture/test_ai_guardrails.py` ·
`frontend/src/lib/api/ai.ts` ·
`frontend/src/components/features/settings/{AiSettingsView,AiSettingsView.test}.tsx` ·
`frontend/src/app/(main)/settings/ai/page.tsx` · `AI_DEVELOPER_GUIDE.md`

## Files modified

`backend/app/core/config.py` (AI settings) · `backend/.env.example` ·
`backend/app/main.py` (AI router) · `frontend/src/types/index.ts` ·
`frontend/src/components/layout/Sidebar.tsx` · `README.md` ·
`CHANGELOG.md` · `AcademicOS_AI_Architecture.md` (appendix) ·
`PATCH_MANIFEST.md` (M11.1 manifest)

## Tests

- Backend: **+109 tests** (unit: DTOs, estimates, config parsing, registry,
  config view, core aggregation, use cases, placeholders; integration:
  full DI-chain API tests for health/providers/models incl. auth gates and
  regression; architecture: 4 new AI guardrails). Full suite green.
- Frontend: **+5 tests** (AI Settings view) — 70 total, tsc clean.

## Verification

- Backend suite: **1351 passed, 2 skipped** (1242 baseline + 109 new AI tests)
- Guardrails: **11/11** (7 domain + 4 AI)
- `tsc --noEmit` clean · `next build` clean
- Manual API: `/ai/health` 200 public · `/ai/providers` + `/ai/models`
  401 without JWT / 200 with · `/health` regression 200

---
# AcademicOS — M10 Release Candidate 1 (RC1) Changelog

Release: **M10 RC1** · Baseline `f891383` (audited M10 HEAD) · Date: 2026-08-07
Status: **feature-frozen; production hardening only — no new functionality**

Sprint M10 passed an independent engineering audit and is frozen. RC1
contains only the release review's low-risk production fixes, verified in
full. All remaining improvements are deferred to Sprint M11 or later.

## Release fixes

| Area | Fix |
|---|---|
| Authenticated downloads | The download endpoints require the bearer token, but the document detail page, `DocumentCard`, `DocumentRow` and `DocumentPreview` rendered plain `<a href={document.url}>` links — an href cannot carry the JWT, so every such click 401'd in production. All four now download through the existing authenticated `downloadDocument` helper via a shared `useDocumentDownload` hook (busy id, no swallowed errors). `downloadDocument` takes the structural `{id, file_name?, title?}` shape, removing the unsound `as never` cast in `ImageViewer` |
| Upload hardening | The document upload route read the whole request body into memory with no cap — an authenticated client could exhaust server RAM. `_read_upload` now enforces the intake pipeline's shared 512 MB cap (`MAX_FILE_BYTES`): a declared-size fast path (where the framework exposes `file.size`) and a chunked read aborting with **413** once the cap is crossed. The upload modal pre-checks the same cap client-side so a doomed transfer never starts |
| Debug code | Removed a leftover `console.log` in `useObjects.ts` |
| Windows launchers | Root `apply_patch.ps1` / `start.ps1` / `stop.ps1` / `health.ps1` still contained em-dashes (the M10.1 polish cleaned `scripts/windows/` but missed the root files); PowerShell 5.1 misreads non-BOM UTF-8 — now ASCII-safe |
| `start_academicos.ps1` | Temp logs now use `[IO.Path]::GetTempPath()` (the `TEMP` env var is not guaranteed in every environment); the final summary reflects the real PostgreSQL / Docker / Qdrant state instead of always printing green `[OK]` |
| `health_check.ps1` | Alembic head check now matches the `(head)` marker Alembic prints instead of a hardcoded `0008`, so future migrations never break the check |
| `apply_patch.ps1` | Deleted files are now backed up like replaced files (they cannot be restored from the patch itself); a single wrapper folder in a patch ZIP is stripped so wrapped and flat archives apply identically (conflict detection and apply previously used the wrong root for wrapped zips); identical files are skipped so re-applying a patch reports **0 Added / 0 Modified** as documented; `PATCH_MANIFEST.md` is installed so the project manifest always reflects the applied state |
| All Windows scripts | **Literal-path file operations** — PowerShell treats `[` `]` in `-Path` as wildcard classes, so Next.js dynamic-route files (`documents/[id]/page.tsx`, `objects/[id]/page.tsx`, …) were **silently skipped** by `apply_patch.ps1` (counted as added, content never replaced). Every `Test-Path` / `Get-Item` / `Get-FileHash` / `Copy-Item` / `Remove-Item` now uses `-LiteralPath`, and directory creation uses `[System.IO.Directory]::CreateDirectory` (`New-Item` has no `-LiteralPath`). Caught by end-to-end verification of the RC1 patch itself against a clean baseline |
| Documentation | `README.md` migration count corrected to `0001..0008`; `FINAL_RELEASE_NOTES.md` added |

## Tests added

- `test_documents_api.py::test_upload_rejects_oversized_files` — HTTP 413 via the chunked read
- `test_documents_api.py::test_read_upload_size_cap` — declared-size fast path, chunked cap, happy path
- `DocumentPreview.test.tsx` — download goes through the authenticated client (no raw href) and failures surface in an alert

## Verification (full suite, 2026-08-07)

- Backend: **1242 passed, 2 skipped** (was 1240 + 2 new cap tests; 2 skips = PostgreSQL-gated JSONB containment)
- Frontend: **65 passed (14 files)** (was 64), `tsc --noEmit` clean, `next build` clean
- Architecture guardrails: **7/7**
- Windows scripts: all 10 parse clean under the PowerShell AST parser; ASCII-safe;
  `apply_patch.ps1` verified end-to-end on PowerShell 7 (apply → re-apply → 0/0/0/0, backups, wrapper-folder strip)
- Manual API verification: upload 201 / oversize 413 / download 200 with JWT / 401 without

---

# AcademicOS — Sprint M10 Final Polish Changelog

Release: **M10 Final Polish** · Baseline `f613b2b` → `HEAD` · Date: 2026-08-07

## Windows automation (audit fixes)

| File | Change |
|---|---|
| `scripts/windows/start_academicos.ps1` | Fixed same-file stdout/stderr redirect bug (separate logs now); fast `TcpClient` port probe replacing slow `Test-NetConnection`; ASCII-safe output |
| `scripts/windows/apply_patch.ps1` | Removed dead backup variable; ASCII-safe output; conflict detection now uses SHA-256 + timestamps consistently |
| `scripts/windows/health_check.ps1` | Fast port probe; DB-file existence check before connecting |
| `scripts/windows/validate_environment.ps1` | Robust Node major-version check (numeric parse); resolves backend dir from any cwd |
| `scripts/windows/stop_academicos.ps1`, `reset_academicos.ps1` | ASCII-safe output |
| All scripts | Unicode (em-dash, ellipsis, checkmarks) removed — ASCII-safe for PS 5.1 on any codepage |

## Frontend fixes

| File | Change |
|---|---|
| `PdfViewer.tsx` | **Controlled page/scale/fitMode props** — the multi-document workspace now genuinely preserves per-tab page/zoom/fit (previously stored but not applied); pdf.js document destroyed on unmount (memory cleanup) |
| `DocumentWorkspace.tsx` | Every tab stays mounted (hidden when inactive) so switching never destroys the pdf and page/zoom/annotations survive; close unmounts → PdfViewer frees the document; fitMode added to tab state |
| `document_viewer` detail page | Live viewer page now drives the CitationPanel page reference (`onPageChange` lifting) |
| `OfficePreview.tsx` + `officeText.ts` | Real DOCX/PPTX/XLSX package parsing with JSZip (readable text/tables/slides) replacing the binary-text approximation; authenticated download fallback (no unauthenticated `<a href>`) |
| `ImageViewer.tsx` | Image error (e.g. TIFF) → inline fallback with authenticated download |
| `KgLinks.tsx` | Fetches the attached AcademicOS object's metadata (committed intake docs) so KG links are populated; document's own object always linked |
| `ExtractedTextPanel.tsx` | Removed duplicate highlight button (SelectionActions owns it); selection preview text |
| `download.ts` | Shared authenticated download helper |

## Tests

- `officeText.test.ts` (5 tests), updated `KgLinks.test.ts`; 64 frontend tests total.

## Verification

- Backend suite: **1240 passed, 2 skipped** (no regressions).
- Frontend: **64 vitest passed**, `tsc --noEmit` clean, `next build` clean.

# AcademicOS — Sprint M10B Changelog (Document Workspace)

Release: **M10B** · Baseline `3f7ed91` (M10A) → `860f2bf` · Date: 2026-08-07

## New features

| Feature | Implementation |
|---|---|
| PDF full-text search | `PdfSearchPanel` (Ctrl+F): match highlighting overlay, Previous/Next, match counter, case-sensitive + whole-word options; pure `searchPdf.ts` matcher (5 tests) |
| Thumbnail sidebar | `ThumbnailSidebar`: lazy-rendered, virtualized page thumbnails, current-page indicator, click-to-jump |
| Multi-document workspace | `DocumentWorkspace` at `/documents/workspace`: tabs, per-tab zoom/page/annotations, close with pdf.js memory cleanup, sessionStorage restore |
| Image viewer | `ImageViewer`: PNG/JPG/JPEG/TIFF/SVG, zoom, pan, fit width/fit screen |
| Office preview | `OfficePreview`: DOCX/PPTX/XLSX read-only browser preview, download fallback |
| Citation workspace | `CitationPanel`: copy citation (academic formatting), page + paragraph references (persistent) |
| AI selection hooks | `SelectionActions`: Explain/Summarize/Rewrite extension points (no fake AI), implemented Highlight/Note/Bookmark |
| Knowledge-graph integration | `KgLinks`: metadata object references → clickable `/objects/{id}` links |
| Accessibility | aria labels, Ctrl+F/Escape/Enter keyboard, focus management, sr-only text |

## Files added
`src/lib/pdf/searchPdf.ts` + test, `PdfSearchPanel.tsx`, `ThumbnailSidebar.tsx`, `DocumentWorkspace.tsx`, `ImageViewer.tsx`, `OfficePreview.tsx`, `CitationPanel.tsx` + test, `SelectionActions.tsx`, `KgLinks.tsx` + test, `src/app/(main)/documents/workspace/page.tsx`, `DocumentViewer.test.tsx` (dispatch).

## Files modified
`DocumentViewer.tsx` (type dispatch), `ExtractedTextPanel.tsx` (selection actions), `PdfViewer.tsx` (search panel + onPdfReady), `documents/[id]/page.tsx` (Citation + KgLinks panels), `src/types/index.ts` (png/jpg/jpeg/tiff/svg), `FileIcon.tsx`.

## Verification
- Backend suite: **1240 passed, 2 skipped** (unchanged — no backend regressions).
- Frontend: **59 vitest passed** (13 new), `tsc --noEmit` clean, `next build` clean.

# AcademicOS — Sprint M10 Changelog

Release: **M10 (Native Document Viewer + Annotation Framework)** · Baseline `c438ff3` → `a3c9935` · Date: 2026-08-07

## Backend — annotations + viewer data

| File | Change |
|---|---|
| `backend/alembic/versions/0008_document_annotations.py` | **new** — `document_annotations` table (annotation_id UUID unique, document_id, type, page, JSONB payload, created_by/at, updated_at; `(document_id, page)` index) |
| `backend/app/infrastructure/db/models/annotation_model.py` | **new** — SQLAlchemy model |
| `backend/app/application/dtos/annotation.py` | **new** — `DocumentAnnotation` record + invariants + factory |
| `backend/app/application/ports/annotation_store.py` | **new** — `AnnotationStore` port (add/get/by_document/update/delete) |
| `backend/app/infrastructure/persistence/annotation_store.py` | **new** — SQL adapter (the review_decision doctrine) |
| `backend/app/application/services/document_annotation_service.py` | **new** — create/list/update/delete + `extracted_text()` resolving the linked intake item via the existing extraction use case |
| `backend/app/api/routes/document_viewer.py` | **new** — viewer routes (below); registered in `main.py` |
| `backend/scripts/init_db.py` | import the annotation model (SQLite quickstart table creation); stamp 0008 |
| `backend/app/tests/unit/test_document_annotations.py` | **new** — 7 tests |
| `backend/app/tests/integration/test_document_annotations_api.py` | **new** — 5 tests |

## Frontend — native viewer

| File | Change |
|---|---|
| `frontend/package.json` / `package-lock.json` | **new dependency** `pdfjs-dist@4.10.38` |
| `frontend/public/pdf.worker.min.mjs` | **new** — pdf.js worker asset (served from /public) |
| `frontend/src/components/features/documents/PdfViewer.tsx` | **new** — in-app PDF render (no download), prev/next/jump, zoom in/out, fit width/page, highlight/note/bookmark overlay |
| `frontend/src/components/features/documents/ExtractedTextPanel.tsx` | **new** — extracted-text pane: select text → highlight (text sync via `findTextHighlight`), page notes, annotation list with delete |
| `frontend/src/components/features/documents/DocumentViewer.tsx` | **new** — side-by-side composition (toggleable); non-PDF keeps the M3 `DocumentPreview` |
| `frontend/src/lib/pdf/textSync.ts` | **new** — pure normalized text→pdf-rect matcher |
| `frontend/src/lib/api/annotations.ts` | **new** — annotations/extracted-text client |
| `frontend/src/app/(main)/documents/[id]/page.tsx` | Preview section now renders `DocumentViewer` |
| `frontend/src/types/index.ts` | annotation + extracted-text types |
| `frontend/src/lib/api/annotations.test.ts`, `frontend/src/lib/pdf/textSync.test.ts`, `frontend/src/components/features/documents/DocumentViewer.test.tsx` | **new** — 13 tests |

## API surface added

- `GET /api/v1/documents/{id}/extracted-text` — linked intake item's extracted text (404 when none)
- `GET|POST /api/v1/documents/{id}/annotations`
- `PUT|DELETE /api/v1/documents/annotations/{annotation_id}`

## Database

- **Migration:** `alembic upgrade head` (0008_document_annotations); SQLite quickstart: `python scripts/init_db.py` (stamps 0008).

## Verification

- Backend suite: **1240 passed, 2 skipped**.
- Frontend: **48 vitest passed**, `tsc --noEmit` clean, `next build` clean.
- Manual: upload PDF → annotation CRUD (highlight/bookmark/note, update, delete, 401 gate) → intake→approve→commit → `extracted-text` returns the pipeline text → highlight persisted → download 200.
# AcademicOS — Final Release Changelog

Release: **1.0.0 (Sprint 8 complete)** · Git: `80892d6` · Date: 2026-08-07

This release closes the gaps found by the forensic audit: the frontend is
now fully functional end-to-end (authentication, route guards, session
management), previously backend-only surfaces are wired into the UI, all
placeholder modules are removed, and fresh-machine bring-up is documented
and verified.

## Authentication (new)

| File | Change |
|---|---|
| `backend/app/api/routes/auth.py` | Added `POST /auth/forgot-password` and `POST /auth/reset-password` |
| `backend/app/application/use_cases/auth/forgot_password.py` | **new** — enumeration-safe reset-token issuance |
| `backend/app/application/use_cases/auth/reset_password.py` | **new** — token-gated password change |
| `backend/app/application/commands/forgot_password.py` | **new** — CQRS command |
| `backend/app/application/commands/reset_password.py` | **new** — CQRS command |
| `backend/app/application/dtos/auth.py` | `ForgotPasswordInput/Output`, `ResetPasswordInput` |
| `backend/app/application/validators/auth.py` | Reset input validation (reuses password rules) |
| `backend/app/application/ports/token_service.py` | `create_reset_token` |
| `backend/app/infrastructure/auth/jwt.py` | `create_reset_token` (type=reset, 30 min TTL) |
| `backend/app/infrastructure/auth/jwt_service.py` | Adapter implements the new port verb |
| `backend/app/core/config.py` | `password_reset_token_ttl_seconds` (default 1800) |
| `backend/app/tests/integration/test_auth_api.py` | +4 reset-flow integration tests |

## Frontend authentication stack (new)

| File | Change |
|---|---|
| `frontend/src/app/(auth)/login/page.tsx` | **new** — login form (Suspense + force-dynamic) |
| `frontend/src/app/(auth)/register/page.tsx` | **new** — registration form |
| `frontend/src/app/(auth)/forgot-password/page.tsx` | **new** — reset-token request (dev transport) |
| `frontend/src/app/(auth)/reset-password/page.tsx` | **new** — token + new password form |
| `frontend/src/components/features/auth/AuthShell.tsx` | **new** — shared shell + form primitives |
| `frontend/src/lib/auth/session.tsx` | **new** — `AuthProvider`/`useAuth`: auto-login, auto-logout, profile load, login/register/logout |
| `frontend/src/lib/auth/token.ts` | Access+refresh storage, session cookie mirror |
| `frontend/src/lib/api/auth.ts` | **new** — register/login/refresh/me/forgot/reset client |
| `frontend/src/lib/api/client.ts` | Single-flight silent refresh on 401 (auth paths excluded) |
| `frontend/src/middleware.ts` | **new** — route guards (protected → `/login?next=`, auth pages → `/`) |
| `frontend/src/app/(main)/layout.tsx` | **new** — client-side session guard |
| `frontend/src/app/layout.tsx` | Wraps the app in `AuthProvider` |
| `frontend/src/components/layout/TopHeader.tsx` | Signed-in user + sign-out |
| `frontend/src/types/index.ts` | `AuthTokens`, `AuthUser`, `ForgotPasswordResult` |
| `frontend/src/app/(auth)/auth-pages.test.tsx` | **new** — 6 render/submit tests |
| `frontend/package.json` | +`@testing-library/user-event` (dev) |

## Previously backend-only surfaces, now wired

| File | Change |
|---|---|
| `frontend/src/lib/api/objects.ts` | `getObjectGraph`, `getGraphPath`, `getObjectAcl`, `updateObjectAcl` |
| `frontend/src/app/(main)/objects/[id]/page.tsx` | Real Relationships + ACL panels (placeholder removed) |
| `frontend/src/lib/api/assistant.ts` | memory recall/consolidate, review pending/approve/reject, eval history |
| `frontend/src/components/features/assistant/AssistantLabs.tsx` | **new** — Memory / Review queue / Evaluation history tabs |
| `frontend/src/app/(main)/assistant/page.tsx` | Renders Assistant Labs |
| `frontend/src/lib/api/intake.ts` | item proposal, regenerate, commit, commit-preview |

## Placeholders removed

| Path | Action |
|---|---|
| `frontend/src/components/features/{ai-chat,administration,projects}/` | deleted (unreferenced) |
| `frontend/src/components/{common,ui}/`, `frontend/src/lib/storage/`, `frontend/src/{stores,styles}/`, `frontend/src/app/api/`, `frontend/src/lib/utils/` | deleted (unreferenced) |
| All `.gitkeep` files under `frontend/src` | deleted (0 remain) |
| `frontend/public/` | favicon.svg added + linked in root layout |

## Configuration / packaging

| File | Change |
|---|---|
| `backend/requirements.txt` | +`alembic==1.13.2` (migrations were unpinnable) |
| `backend/.env.example` | Documents every setting incl. `assistant_*`, `BOOTSTRAP_ADMIN_USERNAME`, `PASSWORD_RESET_TOKEN_TTL_SECONDS` |
| `backend/scripts/init_db.py` | **new** — SQLite quickstart schema + alembic stamp (idempotent) |
| `frontend/src/config/env.ts` | API default `http://127.0.0.1:8000/api/v1` (Windows IPv4-literal) |
| `frontend/.env.example` | Matched template |
| `docker-compose.yml` | **new** — PostgreSQL 16 + Qdrant for the full stack |
| `INSTALL.md` | **new** — Windows/Linux/macOS installation guide |
| `README.md`, `frontend/README.md` | Rewritten for the released state |

## Defects repaired during release verification

| File | Fix |
|---|---|
| `frontend/src/app/(auth)/login/page.tsx`, `reset-password/page.tsx` | `useSearchParams` wrapped in Suspense + `force-dynamic` (prerender failure) |
| `frontend/src/app/(main)/objects/[id]/page.tsx` | `Section` icon-prop misuse (tsc) |
| `frontend/src/lib/api/intake.ts` | Missing `RequestOptions` import |
