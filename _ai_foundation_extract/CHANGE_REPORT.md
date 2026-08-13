# AcademicOS — AI Foundation P0 — Change Report

**ZIP:** `AcademicOS_AI_Foundation_P0.zip`
**Date:** 2026-08-12
**Baseline:** GitHub `feature/m11-ai-workspace` @ `e323102` + ZIP-1 + ZIP-2 (the user's local state). Verified by fresh clones of all three states (A/B/C).
**Scope:** ONE coherent architectural foundation — document-reference resolution, candidate-window integrity, workflow-object exclusion, and the deterministic evidence gate. No auth/upload/streaming/frontend/permission changes. Nothing committed or pushed.

---

## 1. Problem (the real-world failure, freshly reproduced)

The exact browser query
*"According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference? …"*
produced **"CBLU (Chaudhary Bansi Lal University)" with sources `[1] CBLU conference`, `[2] CBLU, Jan 2025.pdf`** — the referenced document absent. Fresh reproduction with a realistic corpus (title ≠ filename; EVENT "CBLU conference"; "CBLU, Jan 2025.pdf"; 10 AI_CONVERSATION objects; intake session "Folder import — Personal"; 6 workshop docs) on all three states:

| State | Plan | SQL limit-8 window | Final retrieval | Target present |
|---|---|---|---|---|
| A pristine | `('cblu',)` | **8 × ai_conversation** | **EMPTY** | ✗ |
| B +ZIP-1 | `('according',)` | — | Galvin | ✗ |
| C +ZIP-1+ZIP-2 | `('cblu',)` | **8 × ai_conversation** | **EMPTY** | ✗ |
| C + **P0** | `document_ref='Cblu Jan, 2024.pdf'` | — | **`[1] Cblu Jan, 2024.pdf`** | **✓** |

**First point of loss (PROVEN):** `sqlalchemy_search_repository.search` applies `LIMIT 8` over ALL types ordered by arbitrary `object_id`, and the internal-type filter runs AFTER the window. With ≥8 conversations matching the term, the window is 100% conversations → post-filter retrieval empty → the LLM answers from conversation history and cites whatever the window happened to contain. The exact-filename term finds the target uniquely in every state — the capability existed; nothing used it.

## 2. Root causes (all PROVEN)

1. **Candidate-window starvation** — internal/workflow types consumed the limit-8 window before exclusion.
2. **No document-reference intent** — a filename in the question was never treated as an exact identifier; only fuzzy `LIKE` on the best single term.
3. **No evidence gate** — generation proceeded unconditionally with empty/wrong evidence; conversation history could satisfy the answer while citations pointed elsewhere.
4. **Workflow objects in evidence** — INTAKE_ITEM/INTAKE_SESSION surfaced as numbered sources via the graph leg ("Folder import — Personal").

## 3. The P0 foundation (files changed — complete replacement files)

### 3.1 `backend/app/infrastructure/repositories/sqlalchemy_search_repository.py`
- New `exclude_types` parameter applied **in the SQL WHERE clause** (never after a limit) — internal/workflow objects can no longer consume the candidate window.
- New `filename` parameter — **exact filename lookup** against the `file_name:` metadata entry (case-normalised; the original upload filename is preserved in metadata, so a user-entered title different from the filename is handled correctly).
- **Relevance ordering** when a text term is present: exact title match ranks first, then deterministic `object_id` tie-break. Arbitrary `object_id` ordering can no longer decide top-k.

### 3.2 `backend/app/application/use_cases/search/search_objects.py`
- Passes `filename` and `exclude_types` through to the repository; applies `exclude_types` to the semantic leg too. Global `GET /search` (no exclusions) is unchanged.

### 3.3 `backend/app/application/services/assistant_retrieval.py`
- New **document-reference intent**: `_document_reference()` detects quoted (`"Cblu Jan, 2024.pdf"`) and bare filenames (anchor on the extension token, walk left over capitalized/numeric name tokens, stop at prose/openers). `RetrievalPlan` gains `document_ref`; the plan carries the exact filename (highest priority intent).
- New `_resolve_document_reference()` — resolves by exact filename, then exact title, with a punctuation-stripped variant fallback — BEFORE any fuzzy term search.
- **Workflow-object exclusion**: `_AI_EVIDENCE_EXCLUDED_TYPES = {AI_CONVERSATION, USER, INTAKE_ITEM, INTAKE_SESSION}` applied at the SQL level (`_exclude_set`), at the term-chain level, and in the graph merge (intake items/sessions never become numbered sources). Memory recall (explicit `ai_conversation` request) remains exempt.
- `AssistantRetrievalResult` (in `dtos/assistant.py`) now carries `document_reference`, `document_reference_resolved`, `resolved_document_id` for the evidence gate.

### 3.4 `backend/app/application/use_cases/ai/grounded_qa.py`
- **Deterministic evidence gate** (`_evidence_gate`), enforced in `execute()`, `stream()`, and `prepare_prompt()`: when the question references a document, the answer is allowed ONLY if that document is in the retrieved evidence set **and** its source text is available; otherwise the assistant returns the honest refusal *"I could not verify the answer from the specified document … I will not answer from other documents or from conversation history."* — no gateway call, no citations.
- `_QA_SYSTEM_INSTRUCTIONS` explicitly demotes CONVERSATION HISTORY to non-citable context (instruction-level reinforcement of the programmatic gate).

### 3.5 Tests
- **New** `backend/app/tests/unit/test_document_reference_resolution.py` (14 tests): plan-level detection (quoted/bare/entity/fact/prose), exact-filename resolution end-to-end, window-starvation prevention with 10 conversations, workflow/internal exclusion in retrieval, global-search unchanged, and the evidence gate (unresolved → refusal; resolved-without-source → refusal; resolved-with-source → passes; stream refusal; non-reference queries unaffected).
- **Updated** `test_retrieval_plan.py` (doc-ref queries now assert the filename term + `document_ref`), `test_retrieval_excludes_internal_types.py` (fake signature).

## 4. Validation results

| Suite | Result |
|---|---|
| Focused: `test_document_reference_resolution.py` + `test_retrieval_plan.py` + `test_retrieval_excludes_internal_types.py` | **56 passed** |
| Retrieval/AI regression (10 suites: fast-streaming, grounded-qa, chat, assistant-retrieval, assistant-memory, content-commit, search-index, hybrid-search, direct-upload-content-search, document-content-search) | **114 passed** |
| **Full backend** | **1,743 passed, 2 skipped** (1,729 baseline + 14 new; 9 Qdrant-server failures pre-existing & environment-only — identical on pristine) |
| `git diff --check` | clean |
| End-to-end realistic trace (10 conversations + 6 workshop docs + intake session) | plan `document_ref` → merged = target → `[1] Cblu Jan, 2024.pdf` → SOURCE block present → conference name inside SOURCE CONTENT |
| Only intended files changed | verified (5 production + 2 updated test files + 1 new test file) |

## 5. Backward compatibility

- All existing plan/retrieval/QA behaviors preserved for non-document-reference queries (35 plan tests unchanged in behavior; entity/fact/count/list queries flow through the existing branches).
- Global search, auth, upload, streaming, permissions, Fix A content indexing, memory recall wiring: untouched.
- `AssistantRetrievalResult`/`RetrievalPlan` new fields are defaulted → legacy constructions compile unchanged.

## 6. Known limitations (deliberately P1+)

- Multi-document references in one query resolve the first filename only (P1: reference lists).
- Claim-level citation verification (LLM-judge over answer vs source text) is P1 — the P0 gate closes the documented failure channel deterministically.
- Body embeddings, semantic thresholds, structured-query routing, cross-tab relationship queries: P2/P3.
- The handoff path (`prepare_prompt`) refuses via a refusal prompt rather than blocking the caller (documented).

## 7. Rollback

Restore the 7 backed-up files + delete the new test file (APPLY_STEPS §8). Pure code change — no migration, no `.env`, no frontend.

## 8. ZIP integrity

- Extracted into a clean temp dir; all packaged files verified **byte-identical** to the final working tree.
- Forbidden-content scan clean (no `.env`, `.git`, node_modules, venv, `__pycache__`, `.pyc`, Docker data, DBs, logs, temp/backup files).
- Path scan: all repository-relative, no absolute paths, no `../` traversal.
- SHA-256: see delivery message.
