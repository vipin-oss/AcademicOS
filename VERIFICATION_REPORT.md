# Verification Report — Sprint M13.3 (Provenance Retrofit + Related Documents)

**Baseline:** `0d93094` (M13.2.1) · **Commit:** `97da723` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** final M13 sprint (two capabilities, reuse-only).

---

## 1. Part A — summarization provenance retrofit

### What was missing
`SummarizeResult` carried only `summary`, `available`, `truncated`, `chars_used`, `chars_total`. The M13.1 contract (`provider_id`, `model`, `prompt_id`, `prompt_version`, `input_tokens`, `output_tokens`, `token_usage_estimated`, `latency_ms`) was absent.

### Fix
`SummarizeDocumentUseCase` already held the real `GenerationResult`; provenance is now populated from it (never fabricated):
- **Success:** `provider_id` from `gateway.provider_id`, `model`/`usage`/`latency` from the result; `prompt_id="ai.summarize"`, `prompt_version=1` (the use case owns this prompt template — honest identity).
- **Fallback:** records only `prompt_id`/`prompt_version`; claims **no** provider/model (none produced one) — internally consistent.
- The summarization safety contract is **unchanged** (master switch, flag, READ, extracted text, 12k truncation, disclosure, untrusted delimiters, honest fallback, non-persistent). `SummarizeResponseModel` exposes the new fields (additive — backward compatible).

### Provenance tests (`test_summarize_document.py::TestProvenance`, 3)
| Test | Asserts |
|---|---|
| `test_success_provenance_from_generation_result` | provider/model/prompt-id/token-usage/latency all from the real result; `available=True`. |
| `test_estimated_usage_when_provider_reports_none` | `token_usage_estimated=True` when the provider reports no counts. |
| `test_fallback_provenance_internally_consistent` | fallback: no provider/model claimed; prompt identity recorded; tokens/latency 0. |

## 2. Part B — `GET /api/v1/ai/related`

### Design (reuse-only)
`RelatedDocumentsUseCase` composes existing components — it constructs **nothing** new:
1. Load + verify source; **READ** on the source before loading/embedding its text.
2. Authoritative source text via `DocumentAnnotationService.extracted_text`.
3. Embed via the **same** `get_embedder` dependency `/search` uses → identical embedder identity + M12 dimensions.
4. `VectorRepository.search` (existing cosine NN, deterministic ordering).
5. Re-authorize every candidate via the **R4** `PermissionEvaluator` gate; exclude the source; cap at `limit`; reuse the existing RRF score convention.

### Contract guarantees
- Source never sent to the embedder without READ; results never returned merely for similarity (READ-filtered); source excluded from its own results; `limit` bounded `[1,50]` (invalid → 422); zero results valid; embedding/vector failures → honest empty; stale index rows never leak; deterministic ordering; no LLM provenance fabricated.

### Configuration authority
`AI_RELATED_DOCUMENTS_ENABLED` (default OFF); gate = `core.config.enabled AND feature_flags["related_documents"]`. `settings` never read directly.

### Related-documents unit tests (`test_related_documents.py`, 16)
| Class | Coverage |
|---|---|
| `TestSourceHandling` | not found (404); READ denied (403); no extracted text (422). |
| `TestHonestDegradation` | no vector repo / no embedder / embed failure / search failure → empty. |
| `TestResultContract` | success fields + score; self-exclusion; unreadable filtered (real evaluator, ACL-restricted obj); stale row never leaks; limit + `limit+1` fetch; limit bounded/clamped; zero results; deterministic ordering. |
| `TestEmbedderReuse` | source text embedded exactly once. |

### Related-documents integration tests (`test_ai_related_api.py`, 8)
| Test | Asserts |
|---|---|
| flag off → 404 · auth required → 401 · flag on proceeds (404 from missing source) | feature gate + auth |
| master switch off (+flag on) → 404 · **no embedding call when disabled** (tracking embedder) | config authority |
| reuses same `HashingEmbedder` identity as `/search` | embedder reuse |
| missing `object_id` → 422 · `limit=0` → 422 | param validation |

## 3. Architecture verification

| Constraint | Status |
|---|---|
| AI Core = single composition authority | ✓ route constructs no providers |
| Route constructs no OpenAI/httpx clients | ✓ |
| Route constructs no embedding adapters | ✓ reuses `get_embedder` |
| Existing `Embedder` port reused (no second abstraction) | ✓ |
| Existing `VectorRepository` reused (no new client/pipeline) | ✓ |
| Permission filtering stays in the application layer (R4 gate) | ✓ |
| No duplicate search pipeline | ✓ |
| Application layer framework-free (no pydantic/httpx in `app.application`) | ✓ 16/16 guardrails |

## 4. Test execution

### 4.1 Targeted (related + summarize provenance + dtos + config)
```
$ python -m pytest app/tests/unit/test_related_documents.py app/tests/integration/test_ai_related_api.py \
    app/tests/unit/test_summarize_document.py app/tests/unit/test_ai_config_view.py app/tests/unit/test_ai_dtos.py -q
58 passed in 3.97s
```

### 4.2 Architecture guardrails
```
$ python -m pytest app/tests/architecture/ -q
16 passed in 4.12s
```

### 4.3 Full backend regression
```
$ python -m pytest app/tests/ -q
1527 passed, 2 skipped in 372.79s
```
1500 → **1527** (+3 summarize provenance, +16 related unit, +8 related integration; **0 failures**). M13.1/M13.2/M13.2.1/M12/M11 all green.

### 4.4 Frontend (unaffected)
```
$ npx vitest run        → 70 passed (15 files)
$ npx tsc --noEmit      → exit 0
```

### 4.5 Lint
```
$ ruff check <all changed files>   → clean
```
(`ai.py`: only the pre-existing FastAPI `B008 Depends()` idiom; integration test: only the accepted `pytest.importorskip` `E402` pattern — both consistent with the rest of the codebase.)

## 5. Repository integrity
- Changed files: 7 modified + 3 new — **all M13.3-scoped**; no unrelated files.
- No stray artifacts (`*.db`, `__pycache__`, `node_modules`).
- `/ai/related` registered (app boots, **269 routes**).
- `ai_related_documents_enabled` defaults **OFF**; wired `config.py → AiConfigView.feature_flags["related_documents"] → route gate`.
- No missing imports/exports (app builds; full suite green).

## 6. Limitations (for the fresh audit)
- Related-docs embedder follows the `semantic_search` flag (shared `get_embedder` dep): with semantic search off, it uses the `HashingEmbedder` fallback (deterministic, non-semantic) — the same honest degradation `/search` uses.
- Scores reuse the search RRF convention on the semantic rank (the vector repository exposes no raw cosine); ordering is the existing vector-search order.
- Summarization provenance is read-only metadata; existing summarization behaviour is unchanged.

## 7. Deliverables
- **Patch ZIP:** `releases/m13.3/m13.3-patch.zip`
- **Patch diff:** `releases/m13.3/m13.3.patch`
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M13.3 entry prepended)

The implementation is left ready for a completely fresh independent audit; M13 final approval is not claimed by this report.
