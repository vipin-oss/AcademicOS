# AcademicOS — Graph-Only Citation Filter (P1 maintenance) — Change Report

**ZIP:** `AcademicOS_GraphCitation_Filter.zip`
**Date:** 2026-08-12
**Baseline:** **`0b83e71`** (`Integrate evidence architecture with P1 chunk retrieval`) on `feature/ai-knowledge-projection-p0` — verified by fresh clone.
**Scope:** the approved P1 maintenance correction from the audit (sections H/I). No retrieval redesign, no FTS/embeddings/vector/ES/LLM-judge/CSV, no new source of truth.

---

## 1. Root cause (confirmed)

A graph-only related object (e.g. the "Ku conference" EVENT discovered via the graph leg's BELONGS_TO traversal from the certificate document) was:
1. **exposed as a citation/source** because `grounded_qa._prepare` built citations from **all** merged `retrieval_result.items` (search hits + graph neighbors) — citations meant "candidates considered", not "evidence used";
2. **leaking its structured metadata into the prompt** (`event.organizer: …`, `event.location: …` rendered under the numbered line in RETRIEVED CONTEXT), which the model echoed as internal-looking labels (`**Organizer**:`, `**Location**:`, `**Title**:`).

Both symptoms share one root cause: graph-only neighbors were treated as citable evidence.

## 2. Exact files changed

| File | Action | Functions changed |
|---|---|---|
| `backend/app/application/use_cases/ai/grounded_qa.py` | modified | `_prepare` (citations from search-hit items only), `_build_source_content` (number-by-id map; unnumbered items never rendered), `_evidence_texts` (same search-hit scope — verifier checks the same evidence the prompt carried) |
| `backend/app/application/assistant/prompt_builder.py` | modified | `build` (RETRIEVED CONTEXT: number-by-id markers; metadata snippet only for citable search-hit items) |
| `backend/app/tests/integration/test_graph_citation_filter.py` | **added** | 7 focused regression tests |

## 3. Exact behavior changes

- **Citations now represent supporting evidence**: `citable = [it for it in retrieval_result.items if "search" in it.sources]` — the existing source classification is reused; no new system invented.
- **Graph-only items** (including documents with text) remain available as **unnumbered contextual lines** (title/type/id/source only) but are never numbered, never rendered in SOURCE CONTENT, and their metadata is suppressed — the `**Organizer**:`-style leak vector is removed.
- **Search-hit items keep everything**: numbering, metadata rendering, SOURCE CONTENT, chunk provenance — structured-object questions ("what is my designation", "when was the Ku conference held") continue to work and remain citable when the object is a genuine search hit.
- **Claim verification** (`_evidence_texts`) now mirrors the prompt's source scope exactly, so the verifier checks the answer against the same evidence the model saw.

## 4. Test results (fresh clone of 0b83e71 + patch)

| Suite | Result |
|---|---|
| New `test_graph_citation_filter.py` | **7 passed** |
| Evidence + chunk + retrieval regression (15 suites, incl. claim_support 26, evidence_contract 16, chunk_evidence_path 7, grounded_qa, chat, streaming, plan, doc-ref, exclusions, P0 chunk suites) | **214 passed** |
| `git diff --check` | clean |
| Frontend (sources render from citations) | 101 passed |
| TypeScript typecheck | 0 errors |

## 5. Certificate regression (real pipeline, fresh clone)

```
Q1 "…exact title of the paper…" → citations = [1] 22 dec.pdf ONLY   ✓ correct answer
Q2 "…who organized the conference…" → citations = [1] 22 dec.pdf ONLY ✓ correct answer
   "Ku conference" NOT a citation; event.organizer/location/acronym NOT in the prompt
Q3 "When was the Ku conference held?" (genuine event search-hit)
   → citations = [1] 22 dec.pdf, [2] Ku conference  ✓ event still citable with metadata
```

## 6. CBLU regression

- Supported verbatim claim through the filtered path: `claim_supported=True`, citation kept.
- Unsupported expansion `"CBLU (Chaudhary Bansi Lal University)"`: refused, no citation (unchanged).

## 7. Preserved invariants (regression-tested)

ACL enforcement (gate precedes merge — unchanged), existence gate, deterministic chunking, chunk span provenance, chunk evidence assembly, claim verification, unsupported-claim refusal, CBLU regression, rebuild equivalence (no index change), single source of truth, single projection writer, document-reference resolution, retrieval exclusions, streaming (shared `_prepare`), structured-object retrieval (search-hit events/faculty keep citation + metadata).

## 8. ZIP contents (repository-relative)

- `backend/app/application/assistant/prompt_builder.py`
- `backend/app/application/use_cases/ai/grounded_qa.py`
- `backend/app/tests/integration/test_graph_citation_filter.py`
- `APPLY_STEPS.md`, `CHANGE_REPORT.md`

No migration required. Nothing committed or pushed.
