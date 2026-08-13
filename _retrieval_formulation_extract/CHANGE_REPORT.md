# AcademicOS — Retrieval Formulation Fix (ZIP-1) — Change Report

**ZIP:** `AcademicOS_Retrieval_Formulation_Fix.zip`
**Date:** 2026-08-11
**Baseline:** GitHub `feature/m11-ai-workspace` @ `e323102` (verified: `e3231026d2cb615c1f8cf0b16297398e2f043ed2`, clean tree) — the patch is built from that exact commit.
**Scope:** query formulation only (`assistant_retrieval.py` + its test file). No commits, no pushes.

---

## 1. Problem

After the upload-auth and content-indexing fixes, asking
*"What is the exact name of the conference mentioned in the Cblu Jan, 2024.pdf? … Quote only the information supported by the document."*
produced an answer ("CERTIFICATE") with **wrong sources** (`[1] Topic20_8p7_Galvin.pdf`, `[2] Folder import — Personal`) — the CBLU PDF was never retrieved, so the LLM answered from unrelated evidence and conversation history.

## 2. Root cause (PROVEN — reproduced on pristine e323102 before any change)

```
Q3 plan on e323102: RetrievalPlan(terms=('mation',), object_type=None)
```

Three deterministic defects in `backend/app/application/services/assistant_retrieval.py`:

1. **Unsafe substring marker matching.** `_TOPIC_MARKERS` contains the bare word `"for"`, and `retrieval_plan()`/`formulate_query()` tested `marker in norm` (substring). `"for"` occurs inside `"in**for**mation"` → the marker branch fired → `formulate_query` sliced after `"for"` → first content token **`'mation'`**. Retrieval then matched unrelated documents (the Galvin paper text contains "mation"-words) or nothing, and the LLM generated an answer with zero current evidence.
2. **Naive capitalization / proper-noun selection.** `_proper_noun()` treated any capitalized non-initial token as an entity: `"January"` in *"Which conference did I attend in January 2024?"* → `terms=('january',)` — the intended type-scoped event search never ran.
3. **Loss of entity signals in document-reference queries.** Sentence-initial tokens were always skipped: *"Cblu Jan 2024"* → `terms=('jan',)` (month) instead of `cblu`; the year/extension signals in the query were unused.

## 3. Evidence

- Pre-fix reproduction on the pristine GitHub tree: `'mation'`, `'jan'`, `'january'` plans (direct `retrieval_plan()` traces).
- Post-fix end-to-end reproduction (full real pipeline, synthetic corpus mirroring the user's setup): all 7 queries now retrieve the CBLU document; the prompt's SOURCE CONTENT contains the conference name and `19 and 20 January 2024` from the PDF body; citations start with `[1] Cblu Jan, 2024.pdf`. Wrong-source contamination gone.

## 4. Exact files changed

| File | Action |
|---|---|
| `backend/app/application/services/assistant_retrieval.py` | overwrite (+107/−18 in diff) |
| `backend/app/tests/unit/test_retrieval_plan.py` | overwrite (+66: 11 new tests) |
| `APPLY_STEPS.md`, `CHANGE_REPORT.md` | new (docs) |

## 5. Exact functions changed (`assistant_retrieval.py`)

- **`retrieval_plan()`** — marker branch now uses `_marker_at(norm)` (word-boundary match) instead of `marker in norm`.
- **`formulate_query()`** — marker slicing now uses `_marker_last_index(norm, marker)` (last whole-word occurrence) instead of `norm.rfind(marker)`.
- **`_proper_noun()`** — (a) skips capitalized common words (`_CAPITALIZED_COMMON_WORDS`: months incl. abbreviations, weekdays, today/yesterday/tomorrow); (b) accepts sentence-initial tokens **only** when the question is a document reference (`_YEAR_RE` year present, or a token ends with a `_DOC_REF_EXTENSIONS` extension like `.pdf`); question/imperative words remain excluded via the existing stopword set.
- **New helpers:** `_marker_at()`, `_marker_last_index()`; new constants `_CAPITALIZED_COMMON_WORDS`, `_DOC_REF_EXTENSIONS`.
- Nothing else touched: term-chain search, singular fallback, object_type handling, year+domain-noun branch, type/count branch, legacy fallback, `_exclude_internal_types`, fusion/ranking, permissions — all unchanged.

## 6. Why this is the smallest correct fix

- The three defects live in one module's query-formulation section; the fix is confined to that file (plus tests).
- Reuses existing seams (stopword set, `_YEAR_RE`, `formulate_query`, plan branches) — no new NLP, no resolver architecture, no new modules.
- Word-boundary regex (`\b…\b`) is the minimal fix for the substring bug; the common-word set and the year/extension gate are small deterministic tables, not heuristics with external dependencies.
- Explicitly NOT implemented (per scope): top-k/relevance redesign, SQL ranking, Qdrant, body embeddings, document-reference resolver, prompt redesign, evidence gate, auth/upload/streaming/frontend/permissions.

## 7. Tests performed

| Suite | Result |
|---|---|
| `test_retrieval_plan.py` — **29 passed** (18 existing + 11 new: the historical `"mation"` regression, document-reference entity preservation, sentence-initial entity with year, month-not-proper-noun, all 6 remaining mandatory CBLU queries, capitalized-Hinglish `Maine` guard, word-boundary markers still working, standalone `for`, `January 2024 conference`) | 29 passed |
| Retrieval/AI regression (retrieval-excludes-internal, fast-streaming, grounded-qa, chat, assistant-retrieval, assistant-memory, content-commit, search-index, hybrid-search, direct-upload-content-search, document-content-search) | **121 passed** |
| **Full backend suite** | **1,723 passed, 2 skipped, 9 pre-existing Qdrant-server failures** (identical on pristine e323102 — require a live Qdrant; unrelated to this patch) |
| `git diff --check` | clean |
| Only intended files changed (`git status`: assistant_retrieval.py + test_retrieval_plan.py) | verified |

## 8. Mandatory regression — before / after

| Query | Before (e323102) | After (this patch) |
|---|---|---|
| "…mentioned in the Cblu Jan, 2024.pdf? …information supported…" | **terms=('mation',)** → wrong/empty retrieval | terms=('cblu',) → CBLU PDF retrieved, body in prompt |
| "Tell me the conference name from Cblu Jan, 2024.pdf" | terms=('cblu',) (OK) | unchanged terms=('cblu',) |
| "Cblu Jan 2024" | terms=('jan',) | terms=('cblu',) |
| "Which conference did I attend in January 2024?" | terms=('january',) | terms=('conference','2024'), object_type='event' |
| "When did I attend the CBLU conference?" / "What was the title…" / "What happened at CBLU in January 2024?" | terms=('cblu',) | unchanged |
| Hindi "maine CBLU me conference attend ki thi…" | terms=('cblu',) | unchanged (+ capitalized "Maine" variant also ('cblu',)) |
| Existing English regressions ("related to mathematics", "quantum entanglement", "my total number of publication", "which papers…2025", "what is my designation") | green | all green (unchanged) |

## 9. Security implications

None. Query formulation is pure, deterministic string logic; no new data access, no permission changes, no new endpoints. Retrieval remains permission-gated at the same points (search use case R4 gate, graph runtime, citation verification).

## 10. What was deliberately NOT changed

`assistant_retrieval.py` search/merge internals, `sqlalchemy_search_repository.py`, Qdrant/vector code, embedder, `grounded_qa.py`, prompt builders, citations, verifier, auth, upload path, streaming, frontend, permissions, intake pipeline, `.env`/Docker. (The top-k truncation and SQL relevance-ordering findings from the audit remain separate future tasks — P1 — not in this ZIP.)

## 11. Regression risk assessment

- Marker branch behavior changes only when a marker appears as a **substring** of another word (the bug case); whole-word marker queries behave as before (proven by tests).
- `_proper_noun` changes only capitalized tokens; lowercase paths identical. Months/weekdays are now excluded from entity detection — the domain-noun branch (with year) takes over, which is the intended behavior for date-style questions.
- Sentence-initial entities are accepted only with a year/extension signal, so Hinglish "Maine…" (no year) is unaffected (tested).
- Worst case for any missed query shape: it falls through to the unchanged domain-noun/fallback branches (same behavior as e323102).

## 12. ZIP integrity

- Extracted into a clean temp dir; both packaged source files verified **byte-identical** to the final working tree.
- Forbidden-content scan: no `.env`, `.git`, node_modules, venv, `__pycache__`, `.pyc`, Docker data, DBs, logs, temp/backup files.
- Path scan: all repository-relative; no absolute paths; no `../` traversal.
- SHA-256: see delivery message (computed on the final ZIP).
