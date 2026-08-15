# ADR-069 — AI-assisted semantic extraction layer (document intake)

- **Status:** Accepted
- **Date:** 2026-08-15
- **Supersedes:** none (extends ADR-067 / ADR-068)
- **Related:** ADR-067 (deterministic document intake), ADR-068 (prose
  extraction + domain-record routing), ADR-059 (AI router), M13.2 structured
  generation (`EnrichDocumentUseCase`)

## Context

The deterministic document-intake pipeline (ADR-067/068) recovers structured
facts from "Label: value" formatting and a small set of natural-language prose
patterns. Real academic documents — conference certificates, publication
front-matter, sanction letters — are frequently written as free prose with no
labels, so the deterministic layer leaves important fields unfilled.

The user's standing requirement: **deterministic extraction is the first
layer; AI semantic extraction is the fallback/enrichment layer when the
deterministic pass cannot obtain important fields.** The AI must **never
invent values**; every AI-derived field must be validated, confidence-gated,
and grounded in the source document.

## Decision

Add an AI semantic extraction layer that:

1. **Runs strictly after** deterministic extraction (labels → prose). It is
   never a parallel or replacement pipeline.
2. **Asks the configured AcademicOS AI provider** — through the existing AI
   Core `structured_generate` (the same M13.2 pattern) — for the *missing*
   schema fields only.
3. **Validates + grounds every value deterministically** before it is
   accepted:
   - *shape* — the response must be a JSON object keyed by predicate id, each
     value `null` or `{"value": str, "confidence": number}` (stdlib-only
     validation, no coercion);
   - *normalisation* — the value is normalised against the predicate catalogue
     (date → ISO, money/number → float, text → collapsed, doi/email/url typed);
   - *confidence* — the AI-reported confidence must meet `AI_ACCEPT_CONFIDENCE`
     (0.8); below it the value is rejected and the document flagged for review;
   - *grounding (anti-hallucination)* — the value must be recoverable from the
     source text (verbatim / date-render / digit-sequence match). A value the
     document does not contain is **rejected**.
4. **Feeds the same dedupe / conflict / claim-write / routing path** as
   deterministic fields (no second write channel). AI-derived claims are
   `PROPOSED` (never `AUTO_SUGGESTED`, never `CONFIRMED`), so the document is
   `review_required` and AI output is never auto-authoritative.
5. **Degrades honestly**: an unavailable/unconfigured provider, malformed
   JSON, a wrong shape, or a gateway failure all yield an empty result —
   deterministic fields are untouched and the document stays usable.

### Extraction precedence

1. Deterministic label / DOI / email / URL / date / amount / number.
2. Deterministic prose patterns (ADR-068).
3. AI semantic extraction (this ADR) — only for fields 1 and 2 missed.

DOI is deterministic-first by construction: the DOI regex runs in layer 1, so
the AI is never even asked for a DOI when one was found; and an AI-supplied
DOI that does not appear in the text is rejected.

### Provenance of AI-derived fields

Every accepted AI field carries: normalized value, `extractor == "ai"`,
AI-reported confidence, the source document id (claim `source_document_id`),
and a `TEXT_RANGE` span locating the value in the source text. The claim
provenance stays `Provenance.INFERRED`.

## Consequences

- **Deterministic-first** remains the invariant: storage never depends on a
  model, and removing the AI seam (absent extractor) yields the exact
  ADR-067/068 behavior.
- **No new domain entities / tables / migrations**: the layer writes claims via
  `ClaimService` and routes via `DomainRecordRouter`, both existing.
- **Anti-hallucination is mechanical**, not model-aspirational: a value that
  is not in the text cannot be stored regardless of what the model says.
- **Honest degradation**: AI low-confidence or ungrounded values leave the
  field empty and set `review_required`, so a human reviews rather than
  auto-committing questionable data.

## Verification

- `backend/app/tests/integration/test_ai_semantic_extraction.py` — grounding
  units, extractor behavior (grounded / low-confidence / ungrounded /
  malformed / unreachable), full intake (conference + publication prose,
  DOI-precedence, AI-unavailable, low-confidence → review), real-socket
  structured generation over a real TCP Ollama stub.
- `backend/app/tests/integration/test_document_intake_ai_api.py` — the
  `POST /documents/{id}/analyze` route exposes `extraction_mode` and
  `extractor == "ai"` fields.
- `backend/app/tests/architecture/test_ai_semantic_extraction_guardrails.py` —
  application-purity, deterministic-first ordering, shared write path.
