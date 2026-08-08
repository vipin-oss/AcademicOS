# Verification Report — Sprint M13.2 (Document Enrichment)

**Baseline:** `96599be` (M13.1.1) · **Commit:** `b52f7f0` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** first production use of structured generation.

---

## 1. Capability

`POST /api/v1/ai/enrich` extracts structured metadata (title, summary, tags,
categories, keywords) from a document's authoritative extracted text using the
AI Core's `LanguageModelGateway.structured_generate()` — the M11.3 capability
activated for the first production use. The endpoint follows the six required
steps:

1. **Verify READ permission** — `PermissionEvaluator.can(READ)` before loading
   text; failure → 403 `PermissionDeniedError`.
2. **Load authoritative extracted text** — `DocumentAnnotationService.extracted_text`
   (the existing intake pipeline; the same source the viewer and summarization use).
3. **Reject documents without extracted text** — `None`/empty → 422 `ValidationError`.
4. **Build a structured-generation prompt** — `StructuredGenerationPrompt` with a
   JSON Schema; document text wrapped in `<<<DOCUMENT>>>`/`<<<END>>>` delimiters.
5. **Use `structured_generate()`** — the gateway returns a parsed JSON object
   (JSON-object response mode); not `generate()`.
6. **Return structured enrichment** — `EnrichmentResult` (title, summary, tags,
   categories, keywords) + truncation disclosure + M13.1 provenance.

## 2. Safety contract (mirrors summarization)

| Concern | Implementation |
|---|---|
| Permission | READ enforced before any text is loaded (403 on failure). |
| Text source | Existing intake pipeline; none/empty → explicit 422 (never an empty enrichment). |
| Truncation | Text > `_MAX_DOC_CHARS` (12000) is truncated AND disclosed (`truncated`, `chars_used`, `chars_total`). |
| Untrusted content | Document text delimited; system instruction says treat as DATA. |
| Structured validation | Model JSON coerced + validated; missing/extra/wrong-type → honest defaults, never crash. |
| Fallback | Gateway unavailable/malformed → `available=False`, empty fields. No crash. |
| Provenance | provider_id, model, prompt_id (`ai.enrich` v1), tokens, latency. |
| Non-persistent | Returned on-demand, never stored. |

## 3. Configuration authority

Enablement is derived **exclusively** through `AiCore.config`:
```python
if not core.config.enabled or not core.config.feature_flags.get("enrichment", False):
    raise HTTPException(status_code=404)
```
`settings` is never read directly (M12.1.1 / M12.3.1 pattern). New flag
`AI_ENRICHMENT_ENABLED` (default off) in `config.py`, projected onto
`AiConfigView.feature_flags["enrichment"]`.

## 4. Regression tests

### 4.1 Unit tests (`test_enrich_document.py`, 15)
| Class | Coverage |
|---|---|
| `TestPermission` | permission denied (403, gateway untouched); document not found (404). |
| `TestExtractedText` | no extraction → 422; empty text → 422. |
| `TestSuccessfulEnrichment` | returns structured fields; uses `structured_generate` not `generate`; untrusted delimiters + schema in prompt; provenance present. |
| `TestStructuredValidation` | missing keys → defaults; wrong types coerced; extra keys ignored. |
| `TestTruncation` | long text truncated + disclosed; short text not truncated. |
| `TestGatewayFallback` | gateway failure → `available=False` + empty fields; malformed value handled. |

### 4.2 Integration tests (`test_ai_enrich_api.py`, 7)
| Test | Asserts |
|---|---|
| `test_enrich_404_when_flag_off` | flag off → 404. |
| `test_enrich_requires_auth` | no auth → 401. |
| `test_unknown_document_404` | missing document → 404 (use case). |
| `test_missing_object_id_field_422` | missing field → 422. |
| `test_ai_disabled_blocks_enrichment_even_when_flag_on` | master OFF + flag ON → 404. |
| `test_no_gateway_invocation_when_ai_disabled` | `structured_generate`/`generate` never called when disabled. |
| `test_ai_enabled_and_flag_on_proceeds` | master ON + flag ON → proceeds (404 from missing doc, not the gate). |

### 4.3 Config-view test
`_StubSettings` + expected `feature_flags` dict updated to include `enrichment`.

## 5. Test execution

### 5.1 Targeted enrichment + config view
```
$ python -m pytest app/tests/unit/test_enrich_document.py app/tests/integration/test_ai_enrich_api.py app/tests/unit/test_ai_config_view.py -q
...........................                                              [100%]
27 passed in 3.52s
```

### 5.2 Architecture guardrails
```
$ python -m pytest app/tests/architecture/ -q
................                                                         [100%]
16 passed in 4.11s
```

### 5.3 Full backend regression
```
$ python -m pytest app/tests/ -q
1484 passed, 2 skipped in 359.54s
```
Baseline 1462 → **1484** (+22 new; **0 failures**). AI Core authority,
transport ownership and the 16 architecture guardrails unchanged.

### 5.4 Frontend regression (unaffected)
Backend-only, additive endpoint + additive flag; the `AiSettingsView` renders
its own fixed `FLAG_LABELS` (unchanged since M11.1 — prior sprints M12.1/M12.3/
M13.1 likewise did not extend it). Confirmed:
```
$ npx vitest run
Test Files  15 passed (15)
     Tests  70 passed (70)
```

### 5.5 Lint
```
$ ruff check app/application/use_cases/ai/enrich_document.py app/tests/unit/test_enrich_document.py
All checks passed!
```
`ai.py` carries only the pre-existing FastAPI `B008 Depends()` idiom shared by
every route (not introduced here). Integration test E402 matches the existing
`pytest.importorskip`-before-imports pattern used by all AI integration tests.

## 6. Constraints honoured

| Constraint | Status |
|---|---|
| No new retrieval pipeline | ✓ reuses intake pipeline |
| No new persistence model | ✓ on-demand, never stored |
| No new embedding system | ✓ |
| No new search implementation | ✓ |
| No new transport owner | ✓ httpx isolation guardrail passes |
| No new provider abstraction | ✓ composition-authority guardrail passes |
| No new AI Core | ✓ |
| No new prompt framework | ✓ inline template + JSON Schema |
| AI Core = single authority | ✓ unchanged |
| Reuse existing DTO/error/permission/fallback | ✓ |
| Backward compatibility | ✓ additive endpoint + flag; no existing shape changed |

## 7. Deliverables
- **Patch ZIP:** `releases/m13.2/m13.2-patch.zip`
- **Patch diff:** `releases/m13.2/m13.2.patch`
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M13.2 entry prepended)
