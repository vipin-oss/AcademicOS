# ADR-067 — V3: intelligent document intake (classify → extract → route → review)

- **Status:** Accepted
- **Level:** V3 (document intake, post-M19)
- **Supersedes:** nothing
- **Related:** ADR-053 (M6 document understanding), ADR-054 (M7 review), ADR-019 (predicate catalogue), ADR-032 (decision audit), ADR-056 (M9 deny-by-default)

## Context

Uploaded PDFs were treated only as searchable documents. The requirement is to
automatically understand a document, extract structured domain facts, and route
them into the appropriate AcademicOS module — with validation, duplicate/
conflict detection, review, provenance, audit, and permission scoping, never a
parallel document system.

## Decision

1. **Extend the M6 document-understanding plane, do not build a new system.**
   The document-type taxonomy (`document_types.py`) is expanded to the full
   academic catalogue (~28 types) with a `target_module` routing label; the
   deterministic classifier (`DocumentClassifier`) is extended to return a
   PRIMARY type plus SECONDARY types (a certificate of participation is also a
   conference + participation), scored by specificity (filename > heading >
   issuer, more keyword hits = more specific) so a generic type never beats a
   specific one.
2. **Structured records are claims.** Extracted fields map to predicates
   (`predicate_catalogue.py`, extended) and are written via the existing
   `ClaimService` — so every record inherits source-document provenance
   (`source_document_id` + spans), ACL scoping, decision audit, and review
   (`PROPOSED` vs `AUTO_SUGGESTED` vs `CONFIRMED`). This is the existing
   structured-fact store the rung-0 / dossier / grounded-QA paths already read,
   so extracted records are retrievable and citable.
3. **Deterministic-first extraction + validation.** Field extraction
   (`document_intake.py` + `value_normalizer.py`) is pure rules/regex: label
   "Label: value" lines, DOI, email, URL, currency amount (currency-marked —
   a bare year/identifier is never an amount), and normalized ISO dates with
   impossible-date rejection. No LLM dependency: storage works with AI
   unavailable; semantic extraction can layer on later via the existing AI path.
4. **Duplicate + conflict detection (never silent overwrite).** Against
   CONFIRMED claims: same predicate + same value → duplicate (skipped, existing
   cited); same predicate + different value → conflict (skipped, review
   required). A conflicting value is never written.
5. **Auto vs review.** A field is AUTO_SUGGESTED only when high-confidence,
   conflict-free and non-duplicate; otherwise PROPOSED (review required).
   Unknown/unparseable documents write nothing (honest).
6. **Routing is data.** `target_module(type_id)` maps a document type to its
   module (research / publications / faculty / teaching / committees / events /
   finance / general_document); one document may route to multiple modules via
   its secondary types.
7. **Surface.** `POST /documents/analyze-upload` and
   `POST /documents/{id}/analyze` return the analysis (type + confidence +
   fields + module + duplicate/conflict + review flag) and are READ/ownership
   permission-scoped.

## Consequences

**Positive**
- Uploads become structured, source-grounded, auditable, idempotent records —
  reusing the frozen claims plane (no parallel tables, no new migration).
- Deterministic-first: honest and dependency-free; provenance is intrinsic.

**Negative / deferred**
- Semantic/free-form extraction (names in prose, multi-line tables) is the
  AI-assisted layer (via the existing enrich/grounded path); the deterministic
  layer covers structured "Label: value" and typed identifiers.
- "Prefer structured records over chunks in grounded QA" is partially realized
  (rung-0/dossier already read confirmed claims); fully ranking structured
  records above document chunks in the open-ended retrieval path is a follow-up.

**Revisit when:** a measurement shows deterministic extraction misses fields an
LLM pass would recover — layer a validated structured-generation step (as the
M13.2 enrich use case already does) onto the deterministic baseline.
