# AcademicOS — Grounded Attribution Fix (ZIP-2) — Change Report

**ZIP:** `AcademicOS_Grounded_Attribution_Fix.zip`
**Date:** 2026-08-11
**Baseline:** GitHub `feature/m11-ai-workspace` @ `e323102` **+ ZIP-1 applied** (the user's exact local state). This ZIP ships the corrected final versions of the two files ZIP-1 changed.
**Scope:** query formulation only (`assistant_retrieval.py` + its test file). No auth, upload, streaming, frontend, permissions, retrieval-architecture changes.

---

## 1. Problem

After ZIP-1, the query
*"According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference? Do not use or expand the acronym CBLU. Do not infer from the filename. …"*
produced a **correct answer with wrong sources**: displayed sources were `[1] Topic20_8p7_Galvin.pdf` and `[2] Folder import — Personal`; the requested `Cblu Jan, 2024.pdf` was not among them.

## 2. Root cause (PROVEN — reproduced on the ZIP-1 state before any change)

ZIP-1 introduced a **sentence-initial entity gate** in `_proper_noun()`: a capitalized sentence-initial token was accepted as an entity whenever the question contained *any* year or file-extension token (`has_doc_ref`). The exact failing query starts with **"According"** — capitalized, sentence-initial, not in the stopword set — so the plan became:

```
ZIP-1 state:  RetrievalPlan(terms=('according',))
```

`'according'` matched the **Galvin paper's body** ("According to the authors …") in SQL; the graph leg then surfaced its intake item (and the intake session "Folder import — Personal" in the user's corpus). The CBLU document never entered retrieval, so the correct conference name could only come from **conversation history** — and the LLM, told to cite "from RETRIEVED CONTEXT ONLY", attached the only available number [1] (Galvin). **Correct answer + wrong citation** — the attribution invariant was violated.

For contrast, pristine `e323102` (without ZIP-1) plans the same query to `('cblu',)` — the defect was introduced by ZIP-1, not present upstream.

## 3. Evidence (all PROVEN)

| Check | ZIP-1 state (before) | This fix (after) |
|---|---|---|
| Plan for exact failing query | `terms=('according',)` | `terms=('cblu',)` |
| Plan for "According to Cblu Jan, 2024.pdf, on what dates…?" | `('according',)` | `('cblu',)` |
| End-to-end pipeline (corpus with Galvin paper, CBLU 2024/2025 PDFs, 10 workshop docs, prior conversation) | Galvin doc+item retrieved; CBLU PDF absent; conference name only in CONVERSATION HISTORY | **Cblu Jan, 2024.pdf retrieved**; its body is a `<<<SOURCE TEXT>>>` block; **conference name inside SOURCE CONTENT**; target document id present in the citations |
| `_proper_noun("According …")` | `'according'` | `None` (falls through to "Cblu" mid-sentence) |
| All 8 mandatory CBLU queries | Q2/Q5 wrong; Q3/Q4/Q6/Q7/Q8 top-k cut | all plan correctly |
| ZIP-1 edge cases (Hinglish "Maine…", markers, months, type/count) | pass | **all still pass** (35 tests) |

## 4. Exact files changed

| File | Action |
|---|---|
| `backend/app/application/services/assistant_retrieval.py` | **overwrite** (complete corrected file — superset of ZIP-1 + fix) |
| `backend/app/tests/unit/test_retrieval_plan.py` | **overwrite** (complete corrected test file — 35 tests) |
| `APPLY_STEPS.md`, `CHANGE_REPORT.md` | new (docs; overwrite the ZIP-1 copies) |

## 5. Exact functions changed (`assistant_retrieval.py`)

- **`_proper_noun()`** — replaced the `has_doc_ref` global gate with a **local document-name pattern check**:
  - sentence-initial capitalized tokens are accepted **only** when they begin a document name: the token itself carries a file extension (`Cblu.pdf`), or the **next significant token** is a capitalized month/weekday (`Cblu Jan 2024`) or a 4-digit year (`Cblu 2024`);
  - `According to …` → next token `to` → rejected → the scan continues and finds `Cblu` mid-sentence → `('cblu',)`;
  - `Maine CBLU me …` → next token `CBLU` (not a month/year) → rejected → `CBLU` found mid-sentence → `('cblu',)` (ZIP-1 behavior preserved);
  - `Cblu Jan 2024` / `Cblu Jan, 2024.pdf` / `Cblu 2024` → accepted → `('cblu',)`.
- **New helper `_starts_document_name(tokens, idx)`** — the local pattern check above.
- **`_QUERY_STOPWORDS`** — added discourse openers (`according`, `accordingly`, `regarding`, `concerning`, `based`, `given`, `following`, `respecting`) as defense-in-depth: they can never become retrieval terms or entities via any path.
- Nothing else touched: marker word-boundary logic (ZIP-1), term-chain search, singular fallback, object_type/year/type-count branches, legacy fallback, exclusions, fusion, permissions — all unchanged.

## 6. Why this is the smallest correct fix

- One function + one helper + a stopword list, all in the existing query-formulation module — no new architecture, no NLP stack, no resolver.
- Fixes the regression at its exact origin (entity selection), so the rest of the pipeline (search, graph, fusion, citations, prompt) works as designed once the plan is right.
- Explicitly NOT implemented (separate future work, per audit): top-k/relevance ordering, internal-type candidate-window consumption, intake-object exclusion from AI sources, deterministic evidence/refusal gate, document-reference resolver architecture, body embeddings.

## 7. Tests performed

| Suite | Result |
|---|---|
| `test_retrieval_plan.py` — **35 passed** (29 ZIP-1 + 6 new: exact failing query, "According to …dates…", discourse-without-doc-ref never entity, mid-sentence entity after opener, year-only and month-only sentence-initial entities) | 35 passed |
| Retrieval/AI regression (11 suites: excludes-internal, fast-streaming, grounded-qa, chat, assistant-retrieval, assistant-memory, content-commit, search-index, hybrid-search, direct-upload-content-search, document-content-search) | **121 passed** |
| **Full backend suite** | **1,729 passed, 2 skipped** (9 pre-existing Qdrant-server failures identical on pristine e323102 — no Qdrant in the sandbox; unrelated to this patch) |
| `git diff --check` | clean |
| Only intended files changed | verified (`assistant_retrieval.py`, `test_retrieval_plan.py`) |
| End-to-end attribution (corpus + conversation history) | target retrieved, body in SOURCE CONTENT, conference name in SOURCE CONTENT, target id in citations |

## 8. Before / after behavior

| Aspect | ZIP-1 state (before) | After this fix |
|---|---|---|
| Plan for "According to the source text of "Cblu Jan, 2024.pdf"…" | `('according',)` → Galvin retrieved, CBLU absent | `('cblu',)` → CBLU PDF retrieved |
| Conference name location in prompt | CONVERSATION HISTORY only | **SOURCE CONTENT** (real document body) |
| Displayed sources for that query | Galvin paper + intake session | CBLU document among them, with matching body |
| Answer/citation integrity | correct answer possible only from history, cited to wrong source | answer and citation reference the same document |
| All previous ZIP-1 behaviors | green | green (unchanged) |

## 9. Security implications

None. Pure deterministic string logic; no new data access, no permission changes, no new endpoints. Retrieval remains permission-gated at the same points (search use case R4 gate, graph runtime, citation verification).

## 10. What was deliberately NOT changed

Auth/upload (`documents.ts`), streaming, frontend, permissions/ACL, intake pipeline, `sqlalchemy_search_repository.py`, Qdrant/vector code, embedder, prompt builders, citations/verifier, `.env`/Docker. (Top-k ordering, internal-type window, intake-object exclusion, and the deterministic refusal gate are separate follow-up items — see CHANGE_REPORT §12 of the prior audit.)

## 11. Regression risk assessment

- Sentence-initial handling changed only for capitalized tokens whose next significant token is **not** a month/weekday/year and that don't carry a file extension — all previously-misaccepted openers now fall through to the mid-sentence scan, which is the correct entity.
- Stopword additions only remove discourse words from consideration — always correct (they are never meaningful retrieval targets).
- Worst case for any unseen query shape: unchanged domain-noun/fallback branches (identical to the ZIP-1 behavior for those paths).
- All 24 plan-level cases (8 mandatory + 16 edge) verified green; the full backend suite is green apart from the known environment-only Qdrant failures.

## 12. ZIP integrity

- Extracted into a clean temp dir; both packaged source files verified **byte-identical** to the final working tree.
- Forbidden-content scan: no `.env`, `.git`, node_modules, venv, `__pycache__`, `.pyc`, Docker data, DBs, logs, temp/backup files.
- Path scan: all repository-relative; no absolute paths; no `../` traversal.
- SHA-256: see delivery message.
