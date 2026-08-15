# ADR-053 — V3 M6: document classification + Wave 1 predicate catalogue

- **Status:** Accepted
- **Level:** V3 M6 (Document Understanding: Classification + Predicate Waves)
- **Supersedes:** nothing
- **Related:** ADR-019 (predicate catalogue), ADR-028 (NIR), ADR-034 (extraction→claim bridge), ADR-050 (local model config), audit A10 (AUTO_SUGGESTED), blueprint §B6 (accuracy gates)

## Context

R1's knowledge plane could only read 3 predicates (`sanctioned_amount`,
`principal_investigator`, `issue_date`) through 11 deterministic label
mappings — the true ceiling on structured answers. Blueprint M6 raises that
ceiling with a Wave 1 document-understanding layer: classify a document's
*semantic* type, then extract that type's facts through a data-driven
template.

Two design constraints from the blueprint and the frozen contract:

1. **Deterministic first, never a strong model.** The classification step is
   `format detect → extract → NIR → CLASSIFY TYPE → template → candidates`.
   Rules (filename, headings, issuer keywords) decide; `FAST_LOCAL` is only a
   deferred tie-break and a strong model is never consulted.
2. **`document_types` + `extraction_templates` are data, not code.** Enabling
   or disabling a type/template is a config change (the M6 rollback path),
   exactly like the ADR-019 additive predicate registry. Tenancy (M15) can
   later make these rows tenant-editable; M6 fixes the shape.

## Decision

1. **Predicate catalogue Wave 1 (data).** `PredicateSpec` gains `unit` and
   `risk_class` (`high` / `low`). The catalogue grows from 3 to 29 predicates
   covering grant/sanction letters (16) and office orders (10) plus shared
   administrative facts (3). A `number` value schema is added (e.g.
   `project_duration_months`), projecting to `value_number` so numeric range
   lookups stay indexed. The three seed predicates keep their ids/versions.
2. **Document types (data).** `document_types.py` registers the two Wave 1
   types with the three deterministic rule families the classifier consults.
3. **Extraction templates (data).** `extraction_templates.py` binds a
   document type to its allowed predicate set. The typed extractor restricts
   candidates to this set; an unknown type falls back to unrestricted
   (best-effort) extraction.
4. **Deterministic classifier (service).** `DocumentClassifier` evaluates
   filename → heading → issuer in priority order; ambiguity falls through to
   `unknown` (no model). A `TextNirParser`-independent `candidate_from_text_lines`
   extractor reads "Label: value" prose so free-form letters/orders are readable.
5. **AUTO_SUGGESTED gates.** `SuggestionPolicy` encodes the blueprint gates:
   high-risk precision ≥ 0.95, low-risk ≥ 0.85, classification accuracy ≥ 0.90.
   A predicate is AUTO_SUGGESTED-eligible only when its *measured* precision
   (from the golden corpus) meets its gate AND the extraction confidence is
   high; **unmeasured or below-gate predicates are disabled** (fail-safe).
   `ClaimService.suggest()` produces the AUTO_SUGGESTED claim (review shortcut,
   never authoritative — A10).

## Consequences

**Positive**
- The system can now read the two most common academic-administration
  documents end-to-end (classify → extract → propose/suggest).
- Predicate taxonomy and templates are additive data — new document types
  (Wave 2: appointment letters, PhD records, publications, invoices) extend
  the registry without code.
- AUTO_SUGGESTED is gated by measurement, mechanically preventing machine
  output from becoming authoritative truth (A10).
- No new schema beyond the M5 typed columns; `number` maps to the existing
  `value_number`.

**Negative / deferred**
- The classifier is rule-based, so coverage is bounded by the Wave 1 keyword
  set; `FAST_LOCAL` tie-breaking is explicitly deferred (ADR-050 configures a
  local model when a measurement justifies it).
- `document_types` / `extraction_templates` are in-repo data, not yet
  tenant-editable rows — that is M15 (tenancy) work, not M6.
- The existing `NirMapper.write_claims` path (tables/sheets/metadata) is
  unchanged; the typed extractor is an additive Wave 1 surface. Unifying the
  two is M11 (One Document Pipeline) work.

**Revisit when:** a measurement shows the deterministic classifier misses
real documents that a `FAST_LOCAL` tie-break would catch — then wire the
local model per ADR-050, still never a strong model for classification.
