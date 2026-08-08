# Verification Report — Sprint M13.2.1 (Corrective — Structured-Output Contract Hardening)

**Baseline:** `0377aec` (M13.2) · **Commit:** `fc40127` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** corrective only.

---

## 1. Design decision — where to enforce the schema

The audit offered two acceptable locations: validate at the structured-generation
boundary, or enrichment-specific immediately after `structured_generate()`.

**Chosen: enrichment-specific validation immediately after `structured_generate()`.**

Rationale:
1. **Frozen transport owner.** `OpenAIProvider` is the single M11 transport owner.
   Embedding enrichment-specific validation (or a generic JSON-Schema validator +
   new dependency) inside it changes the frozen M11 structured-generation
   contract. The sprint forbids touching the transport owner / redesigning the
   AI Core. The gateway is therefore **unchanged** — zero regression risk for
   the shared `structured_generate()` contract.
2. **Contract ownership.** The enrichment shape (field names, types, extra-field
   policy) is owned by the enrichment use case, not the generic gateway.
3. **Endorsed fallback.** The audit explicitly permits enrichment-specific
   validation "immediately after `structured_generate()`" when a shared-contract
   change is risky.

This satisfies DEFECT 1: the schema **is** enforced (just at the use-case
boundary), using the same `_ENRICHMENT_SCHEMA` asserted to the model.

## 2. Validation mechanism

- **Stdlib-only**, schema-driven: `_validate_against_schema(value, schema)` +
  `_validate_property` + `_check_type` use only `isinstance`. They interpret the
  JSON-Schema *subset* the enrichment schema declares: `type` (object/string/
  array), `required`, `properties`, `items.type`, `additionalProperties`.
- **Single source of truth.** `_ENRICHMENT_SCHEMA` is asserted to the model via
  `StructuredGenerationPrompt.schema` **and** used to validate the output. There
  is no second, hardcoded copy of the field rules.
- **Strict, no coercion.** `123` for a `string` field is rejected (not coerced
  to `"123"`); `None` rejected; `"physics"` for an array rejected; non-string
  array items rejected; missing required fields rejected; unexpected fields
  rejected (`additionalProperties: false`). `bool` is guarded against `int`.
- **Not used:** `pydantic` — the M11 guardrail
  `test_application_depends_only_on_domain_and_stdlib` forbids framework imports
  in `app.application` (the DTOs use stdlib `dataclasses`, not pydantic). This
  was caught and corrected during the sprint. `jsonschema` is not a dependency.
  A focused stdlib validator is the smallest correct, safe implementation.

## 3. DEFECT 1 — schema now enforced

| Before | After |
|---|---|
| `structured_generate()` parsed JSON and checked only `isinstance(value, dict)`; `prompt.schema` was ignored. | The use case validates `result.value` against `_ENRICHMENT_SCHEMA` (the same schema sent to the model). Arbitrary objects / wrong shapes are rejected → `available=False`. |

## 4. DEFECT 2 — permissive coercion removed

| Before (`_coerce`) | After (`_validate_against_schema`) |
|---|---|
| `title=123 → "123"`, `summary=None → ""`, `tags="physics" → ("physics",)`, `categories=42 → ()`, missing keys → defaults, extra keys ignored. Result: `available=True`. | Any violation raises `_SchemaValidationError` → `available=False` with empty fields. No coercion. Invalid output never reaches the success path. |

Required contract now enforced: `title`/`summary` required `string`; `tags`/
`categories`/`keywords` required `array<string>`; extra fields rejected.

## 5. Audit regression matrix (21 points)

| # | Test | Result |
|---|---|---|
| 1 | valid enrichment passes | ✅ `test_valid_enrichment_passes` |
| 2–6 | missing title / summary / tags / categories / keywords | ✅ parametrized |
| 7–8 | `title=None`, `summary=None` | ✅ parametrized |
| 9 | `tags="physics"` (scalar) | ✅ parametrized |
| 10 | `categories=42` | ✅ parametrized |
| 11 | `keywords=["ok",7]` (non-string item) | ✅ parametrized |
| 12 | extra-field policy (reject) | ✅ `[extra_field]` + `test_schema_is_strict_no_additional_properties` |
| 13 | invalid JSON | ✅ `test_invalid_json_is_rejected` (gateway raises → fallback) |
| 14 | arbitrary JSON object | ✅ `[arbitrary_object]`, `[empty_object]` |
| 15 | invalid → `available=False` | ✅ `test_invalid_output_returns_available_false` |
| 16 | invalid skips success path | ✅ `test_invalid_output_does_not_reach_success_path` (a valid-in-isolation field stays empty) |
| 17 | provider failure → fallback | ✅ `test_provider_failure_returns_honest_fallback` |
| 18 | valid provenance preserved | ✅ `test_valid_provenance_preserved` |
| 19 | fallback provenance consistent | ✅ `test_fallback_provenance_internally_consistent` |
| 20 | `AI_ENABLED` master switch blocks | ✅ integration `test_ai_disabled_blocks_enrichment_even_when_flag_on` |
| 21 | `AI_ENRICHMENT_ENABLED` blocks | ✅ integration `test_enrich_404_when_flag_off` |

Existing permissive-coercion tests (`test_missing_keys_default_to_empty`,
`test_wrong_types_coerced`, `test_extra_keys_ignored`,
`test_malformed_structured_response_is_handled`) were **rewritten to assert
rejection**, not weakened.

## 6. Test execution

### 6.1 Targeted (enrichment + shared structured_generate + config)
```
$ python -m pytest app/tests/unit/test_enrich_document.py app/tests/integration/test_ai_enrich_api.py \
    app/tests/unit/test_openai_adapter_hardening.py app/tests/unit/test_ai_placeholders.py \
    app/tests/unit/test_ai_dtos.py app/tests/unit/test_ai_config_view.py -q
103 passed in 3.48s
```

### 6.2 Architecture guardrails
```
$ python -m pytest app/tests/architecture/ -q
16 passed in 4.05s
```

### 6.3 Full backend regression
```
$ python -m pytest app/tests/ -q
1500 passed, 2 skipped in 381.98s
```
1484 → **1500** (permissive tests replaced by strict-rejection + the full audit
matrix; **0 failures**). The gateway is unchanged — every existing structured-
generation test passes.

### 6.4 Frontend (unaffected)
```
$ npx vitest run        → 70 passed (15 files)
$ npx tsc --noEmit      → exit 0
```

### 6.5 Lint
```
$ ruff check app/application/use_cases/ai/enrich_document.py app/tests/unit/test_enrich_document.py
All checks passed!
```

## 7. Constraints honoured

| Constraint | Status |
|---|---|
| No new features / redesign / persistence | ✓ only the two defects |
| Do NOT change search/embedding/QA/M13.3 | ✓ untouched |
| Do NOT introduce a new transport owner | ✓ gateway unchanged |
| Do NOT introduce a new provider | ✓ |
| Maintain architecture guardrails | ✓ 16/16 (incl. application framework-free) |
| No second schema definition | ✓ `_ENRICHMENT_SCHEMA` is the single source |
| No permissive coercion / no fabrication | ✓ strict validation |
| Do not weaken existing tests | ✓ permissive tests rewritten to assert rejection |

## 8. Remaining limitations (for the fresh audit)
- Validation covers the JSON-Schema subset the enrichment schema uses
  (`type`/`required`/`properties`/`items`/`additionalProperties`). It is not a
  general JSON Schema implementation — by design (smallest correct, scope-bound).
- Schema enforcement is enrichment-specific, not at the gateway boundary (the
  audit's endorsed fallback; keeps the transport owner frozen). A future second
  structured-generation caller must validate its own contract at its boundary.
- The gateway still sends `response_format: {"type": "json_object"}` only (JSON
  Schema is not pushed to the provider wire) — consistent with the M11 design;
  the schema is enforced in-application.

## 9. Deliverables
- **Patch ZIP:** `releases/m13.2.1/m13.2.1-patch.zip`
- **Patch diff:** `releases/m13.2.1/m13.2.1.patch`
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M13.2.1 entry prepended)
