# AcademicOS M13.2.1 — Incremental Patch Manifest (Corrective — Structured-Output Contract Hardening)

**Baseline:** `0377aec` (M13.2) · **Commit:** `fc40127` · **Date:** 2026-08-08
**Scope:** corrective only — two M13.2 audit defects. No new features, no gateway change, no new abstraction, no new dependency.

## Files Changed

| Path | Change |
|---|---|
| `backend/app/application/use_cases/ai/enrich_document.py` | Removed permissive `_coerce()`. Added stdlib-only, schema-driven `_validate_against_schema()` (+ helpers). `_ENRICHMENT_SCHEMA` gains `additionalProperties: false` and is the single source of truth (asserted to the model AND used for validation). Invalid structured output → `available=False` fallback; never reaches the success path. |
| `backend/app/tests/unit/test_enrich_document.py` | Permissive-coercion tests rewritten to assert **rejection**; full 21-point audit regression matrix (#1–#19 use-case level; #20–#21 in the existing integration suite). |

## Exact validation mechanism
- **Location:** enrichment-specific, immediately after `structured_generate()` (the audit's endorsed fallback; keeps the frozen M11 transport owner untouched).
- **Mechanism:** stdlib `isinstance` checks driven by the JSON-Schema subset the enrichment schema uses (`type`, `required`, `properties`, `items.type`, `additionalProperties`). No coercion.
- **Single schema:** `_ENRICHMENT_SCHEMA` — asserted to the model via `StructuredGenerationPrompt.schema` AND used to validate output. No second definition.
- **Not used:** `pydantic` (forbidden in `app.application` by the M11 architecture guardrail); `jsonschema` (not a dependency); `OpenAIProvider.structured_generate()` (unchanged).

## Enrichment contract (enforced)
`title`/`summary`: required `string` · `tags`/`categories`/`keywords`: required `array<string>` · extra fields: rejected (`additionalProperties: false`). Violations → `available=False`, empty fields, consistent provenance.

## Audit regression matrix (21 points)
| # | Coverage | Location |
|---|---|---|
| 1 valid passes · 2–6 missing each field · 7–8 None · 9 scalar-for-array · 10 wrong type · 11 non-string item · 13 invalid JSON · 14 arbitrary object | `test_invalid_output_is_rejected` (parametrized) + `test_valid_enrichment_passes` + `test_invalid_json_is_rejected` | unit |
| 12 extra-field policy | `test_invalid_output_is_rejected[extra_field]` + `test_schema_is_strict_no_additional_properties` | unit |
| 15 invalid→available=False · 16 invalid skips success path | `TestInvalidOutputContract` | unit |
| 17 provider failure → fallback | `TestGatewayFallback` | unit |
| 18 valid provenance · 19 fallback provenance consistent | `TestProvenance` | unit |
| 20 AI_ENABLED blocks · 21 AI_ENRICHMENT_ENABLED blocks | `test_ai_disabled_blocks_enrichment_even_when_flag_on`, `test_enrich_404_when_flag_off` | integration |

## Verification
- Backend: **1500 passed, 2 skipped** (zero failures)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean on changed files
