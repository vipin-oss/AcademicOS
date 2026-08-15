# ADR-068 — V3: domain-record routing, prose extraction, and conversational guard

- **Status:** Accepted
- **Level:** V3 (document intelligence completion)
- **Supersedes:** nothing (extends ADR-067)
- **Related:** ADR-067 (document intake), ADR-053 (M6), ADR-019 (predicates), ADR-056 (M9)

## Context

ADR-067 made uploads produce CLAIMS only; the requirement is automatic
placement into the ACTUAL AcademicOS domain modules, semantic extraction from
prose (not only "Label: value"), structured-retrieval priority, and a
conversational-query guard.

## Decision

1. **Domain-record routing.** `DomainRecordRouter` maps a classified document
   to a real domain record via the frozen create use cases, with their
   duplicate detection:
   - conference / conference_* / event / university_notice → **Event**
     (`event_type="conference"`);
   - publication / journal_article / book_chapter / patent → **Publication**;
   - grant / grant_sanction_letter / research_project → **Research Project**;
   - committee → **Committee**.
   A duplicate (existing DOI / title+date / code / name) skips creation and
   reports the existing record; a conflict (same identity, different value)
   is treated as a duplicate for safety. Provenance is a `RELATED_TO` edge
   from the record to the source document, plus the claims' source binding.
   Types with NO matching entity (award, appointment, experience, promotion,
   teaching/course, syllabus, timetable, student_record, phd_progress,
   finance_invoice, purchase, certificate, correspondence, general_document)
   stay **claim-only** — a structured fact bound to the source document,
   never a fabricated entity.
2. **Prose semantic extraction (deterministic).** `prose_extractor` recovers
   facts from natural-language certificate/letter phrasing (recipient,
   presentation title, conference name, organizer, venue, and "from X to Y"
   date spans) with anchored patterns. Deterministic-first: no LLM
   dependency; AI-assisted extraction can layer on later.
3. **Conversational guard.** `retrieval_plan` returns an empty plan for pure
   small-talk/liveness questions (no domain noun, no document reference), so
   "are you working?" no longer runs broad document retrieval — while
   "are you working on my research project?" still retrieves (domain noun).
4. **Structured-retrieval priority is realized structurally.** Because
   conference/publication/project/committee records are now real Objects,
   the existing `_DOMAIN_NOUN_TO_TYPE` type-scoped retrieval
   ("conferences" → EVENT, "papers" → PUBLICATION, …) retrieves the
   structured records directly, and the graph leg follows membership edges —
   so structured records rank above arbitrary document chunks by construction.

## Consequences

**Positive**
- Uploads now create real, deduplicated, provenance-linked domain records
  where the model exists; everything else degrades to a source-bound claim.
- Prose is understood without labels and without an LLM.
- Conversational queries no longer leak unrelated documents.

**Negative / deferred**
- Claim-only types remain for entities the system does not yet model as
  first-class create use cases (notably faculty awards/experience, which are
  embedded in the Faculty profile, and student/PhD/finance records).
- AI-assisted semantic extraction (beyond deterministic prose) is the
  documented next layer, reusing the enrich structured-generation pattern.

**Revisit when:** a measurement shows deterministic prose misses fields an LLM
pass would recover — add a validated structured-generation extraction step
behind the existing gateway, still gated by the review/confidence policy.
