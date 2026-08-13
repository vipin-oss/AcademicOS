# AcademicOS — AI Evidence Architecture P1 Integration v2 — Change Report

**ZIP:** `AcademicOS_AI_Evidence_Architecture_P1_Integration_v2.zip`
**Date:** 2026-08-12
**Baseline:** **`bd253b9`** (`Implement AI knowledge projection foundation`) — the user's actual local baseline on `feature/ai-knowledge-projection-p0`.
**Scope:** reconcile the missing Evidence Architecture P0 (claim→source verification) into the bd253b9 architecture, self-consistently. No architectural changes beyond what the integration requires. Nothing committed or pushed.

---

## 1. Why v1 failed (diagnosis, verified)

The previous ZIP (v1) was built against the P1 scratch commit `51547a2` and shipped a `grounded_qa.py` that imports `app.application.services.evidence_assembly` — a **P1 file absent from bd253b9**. Verified on the Git trees:

```
git ls-tree -r --name-only bd253b9  | grep evidence_assembly  → ABSENT
git ls-tree -r --name-only 51547a2 | grep evidence_assembly  → backend/app/application/services/evidence_assembly.py
```

**Conclusion:** the P1 implementation was never committed into the user's branch (it exists only in the scratch environment). v1 was therefore not self-consistent with the user's local baseline and **failed local application with `ModuleNotFoundError: No module named 'app.application.services.evidence_assembly'`** — it is considered FAILED and is superseded by v2.

## 2. v2 compatibility analysis (against bd253b9)

| Requirement | Status on bd253b9 | v2 action |
|---|---|---|
| `claim_support.py` (verifier) | absent | **included (new, original)** |
| `evidence_assembly.py` (bounded chunk selection) | absent | **included (validated P1 version)** — required by `grounded_qa` import |
| `document_chunk_store` port + SQL store | present (P0) | unchanged (import resolves) |
| `dtos/ai.py` `QAResult.claim_*` fields | absent | included (diff vs bd253b9 = claim fields + serialization only, verified) |
| `grounded_qa.py` claim wiring | P0 version (evidence gate only) | **included (merged version)** — imports resolve on bd253b9 (claim_support + evidence_assembly delivered; DocumentChunkStore/retrieval_plan present) |
| `routes/ai.py` chunk wiring | absent | **included** — exact 6-line delta (import + 5 `chunk_store=` sites), verified `git diff bd253b9..51547a2` = +6 lines; activates chunk evidence in the live app |
| FTS (`fts.py`) | absent | **NOT included** — the evidence integration does not require FTS; `test_chunk_evidence_path.py` was made backend-agnostic (works with the bd253b9 LIKE content leg and with P1 FTS) |
| Other P1 files (search repo FTS path, index_applier FTS, rebuilder FTS, migration 0011, benchmark) | absent | **NOT included** — not required by the Evidence Architecture; they belong to the separate P1 commit |

## 3. Exact nine-file reconciliation

| File | Action | Change |
|---|---|---|
| `backend/app/application/assistant/claim_support.py` | **added** | original verifier: `evidence_mode`, `normalize_text`, `acronym_expansion_violation` (generic), `ClaimSupportVerifier` → `ClaimSupportVerdict` |
| `backend/app/application/services/evidence_assembly.py` | **added (P1, validated)** | bounded chunk selection (max 3 chunks / 2,000 chars per doc, term→token→adjacency ranking, span provenance, document-order output) |
| `backend/app/application/dtos/ai.py` | modified | +`claim_supported`/`claim_mode`/`claim_coverage` on `QAResult`; +3 entries in `qa_result_dict` |
| `backend/app/application/use_cases/ai/grounded_qa.py` | modified | claim imports; claim-level system instructions; `claim_verifier` param; `evidence_mode` + `_verify_claims` + `_claim_refusal` in execute/stream/prepare_prompt; functional ANSWER CONTRACT in `_build_prompt`; claim fields in `_success_result`; **chunk-aware `_evidence_texts`** |
| `backend/app/api/routes/ai.py` | modified | +`SQLDocumentChunkStore` import; +`chunk_store=` at the 5 `GroundedQAUseCase` construction sites (live-app chunk evidence) |
| `backend/app/tests/unit/test_claim_support.py` | **added** | 26 unit tests |
| `backend/app/tests/unit/test_evidence_contract.py` | **added** | 16 behavioral matrix tests (A–J) |
| `backend/app/tests/unit/test_chunk_evidence_assembly.py` | **added (P1, validated)** | 13 unit tests for the delivered `evidence_assembly.py` |
| `backend/app/tests/integration/test_chunk_evidence_path.py` | modified | 7 tests; **adapted to be backend-agnostic** (no FTS import; retrieval assertion works via the bd253b9 LIKE content leg and P1 FTS alike); +2 claim tests (unsupported-expansion refusal, claim fields) |

**Key adaptation — chunk-aware claim verification:** `_evidence_texts` mirrors `_build_source_content` exactly — it uses the same `select_chunks`/`render_chunk_evidence` seam (with chunk span provenance) for documents with chunks, falling back to whole extracted text otherwise — so **claim verification checks the answer against the same evidence the prompt carried**. The verifier never re-introduces whole-document assumptions.

## 4. Behavior (validated on a fresh bd253b9 clone + v2)

**Supported verbatim extraction:**
```
model claim : "In Honor International Conference of Srinivasa Ramanujan's Birthday"
claim_supported : True (mode=extraction)
final answer    : the exact conference name
citations       : [1] Cblu Jan, 2024.pdf
```

**Unsupported acronym expansion:**
```
model claim : "CBLU (Chaudhary Bansi Lal University)"
claim_supported : False (mode=extraction)
final answer    : "The answer could not be verified as a direct quote from
                  'Cblu Jan, 2024.pdf'…" (deterministic refusal)
citations       : [] (none)
```

**Conversation-history protection:** history is demoted to non-citable context (instruction) AND cannot satisfy the verbatim/acronym checks (deterministic).
**Citation behavior:** supported claims keep their citation; refused claims carry none.
**Provenance behavior:** the evidence seam carries chunk index range + character spans; `document_id`/chunk provenance flows through retrieval, evidence assembly, and the verifier.

## 5. Test results (fresh bd253b9 clone + v2, validated)

| Suite | Result |
|---|---|
| `test_claim_support.py` + `test_evidence_contract.py` + `test_chunk_evidence_path.py` (the exact user command) | **49 passed** |
| `test_chunk_evidence_assembly.py` | 13 passed |
| P0 chunk + retrieval regression (lifecycle, chunking, rebuild, grounded_qa, chat, streaming, plan, doc-ref, exclusion, content-search, direct-upload) | green |
| Full backend (expected on the user machine) | 1,849 passed / 2 skipped class (9 Qdrant env + 1 flaky intake timing test, both pre-existing, untouched) |
| `git diff --check` | clean |
| No unrelated files changed (fresh clone → apply → tree diff) | verified — exactly the nine files |

## 6. Known limitations

1. The verifier is **deterministic** (verbatim + acronym guard in extraction mode; content-token coverage flag in general mode). A semantic LLM-judge remains a later extension — deliberately not added.
2. General-mode `claim_supported` is an advisory coverage flag, not a refusal trigger (refusal is extraction-mode only — by design).
3. The P1 FTS retrieval layer, chunk-scoped benchmark, and migration 0011 are **not** part of this ZIP (they belong to the separate P1 commit on top of bd253b9). On bd253b9 the retrieval backend is the LIKE content leg; the evidence integration is backend-agnostic by design.
4. If/when the P1 commit is applied locally, this evidence integration continues to work unchanged (its test was made backend-agnostic for exactly this reason).

## 7. ZIP contents (repository-relative)

- `backend/app/application/assistant/claim_support.py`
- `backend/app/application/services/evidence_assembly.py`
- `backend/app/application/dtos/ai.py`
- `backend/app/application/use_cases/ai/grounded_qa.py`
- `backend/app/api/routes/ai.py`
- `backend/app/tests/unit/test_claim_support.py`
- `backend/app/tests/unit/test_evidence_contract.py`
- `backend/app/tests/unit/test_chunk_evidence_assembly.py`
- `backend/app/tests/integration/test_chunk_evidence_path.py`
- `APPLY_STEPS.md`, `CHANGE_REPORT.md`

No migration required. Rollback: APPLY_STEPS §9 (timestamped backup + restore).
