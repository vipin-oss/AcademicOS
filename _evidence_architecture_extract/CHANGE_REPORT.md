# AcademicOS — AI Evidence Architecture P1 Integration — Change Report

**ZIP:** `AcademicOS_AI_Evidence_Architecture_P1_Integration.zip`
**Date:** 2026-08-12
**P1 baseline:** `51547a2` (`feat(ai): P1 retrieval layer — FTS projection, chunk evidence assembly, bounded retrieval`) on `feature/ai-knowledge-projection-p0`.
**Scope:** reconcile the missing Evidence Architecture P0 (claim→source verification) into the frozen P1 architecture. No architectural changes to P1. Nothing committed or pushed.

---

## 1. Original Evidence Architecture implementation source

The original deliverable is the earlier `AcademicOS_AI_Evidence_Architecture_P0.zip` (present in the workspace). It contains: `backend/app/application/assistant/claim_support.py` (the claim verifier), `backend/app/application/dtos/ai.py` (claim fields + serialization), `backend/app/application/use_cases/ai/grounded_qa.py` (claim wiring), and the two test files. The original `claim_support.py` and both test files are restored **verbatim**.

## 2. Why it was missing from bd253b9

`bd253b9` (`Implement AI knowledge projection foundation`) was created by consolidating the delivered ZIPs into one commit — but the Evidence Architecture ZIP was **not among the consolidated set**. The branch therefore contains the earlier document-reference/evidence **gate** (`_evidence_gate`, doc-ref resolution) but **not** the claim→source verification layer (`claim_support.py`, `QAResult.claim_*` fields). This was confirmed by the P1 audit and is now repaired on top of the frozen P1 commit.

## 3. Compatibility analysis with P1 (51547a2)

| Old layer piece | Conflict with P1? | Resolution |
|---|---|---|
| `claim_support.py` | none (standalone, deterministic) | restored verbatim |
| `QAResult.claim_supported/claim_mode/claim_coverage` | none | added + serialized in `qa_result_dict` (`domain_assistant_result_dict` inherits) |
| `_verify_claims` / `_claim_refusal` | old `_evidence_texts` used whole-document text | **P1-adapted**: verifies against the actual chunk/source evidence the prompt used |
| `_build_prompt` ANSWER CONTRACT | old version lacked P1's `evidence_term` | merged (mode functional, evidence_term preserved) |
| `execute` / `stream` / `prepare_prompt` | P1 added observability + evidence term | claim check inserted after citation verification; observability untouched |
| System instructions | P1 already had history demotion | claim-level rules added (acronym, title-is-label, say-so) |
| FTS / chunk assembly / ACL / citations | none | untouched |

## 4. Exact six-file reconciliation

| File | Action | Change |
|---|---|---|
| `backend/app/application/assistant/claim_support.py` | **added (restored)** | the original verifier: `evidence_mode`, `normalize_text`, `acronym_expansion_violation` (generic), `ClaimSupportVerifier` → `ClaimSupportVerdict` |
| `backend/app/application/dtos/ai.py` | modified | +`claim_supported`/`claim_mode`/`claim_coverage` on `QAResult`; +3 entries in `qa_result_dict` |
| `backend/app/application/use_cases/ai/grounded_qa.py` | modified | imports; claim-level system instructions; `claim_verifier` param; `evidence_mode` + `_verify_claims` + `_claim_refusal` in execute/stream/prepare_prompt; functional ANSWER CONTRACT in `_build_prompt`; claim fields in `_success_result`; **chunk-aware `_evidence_texts`** |
| `backend/app/tests/unit/test_claim_support.py` | **added (restored)** | 26 unit tests |
| `backend/app/tests/unit/test_evidence_contract.py` | **added (restored)** | 16 behavioral matrix tests (A–J) |
| `backend/app/tests/integration/test_chunk_evidence_path.py` | modified | +2 tests: unsupported-expansion refusal through the chunk path; claim fields on the supported path |

**Key adaptation — chunk-aware claim verification:** the old verifier checked claims against the whole extracted document text. In P1, the model receives **bounded chunk evidence** (max 3 chunks / 2,000 chars per document, with `(chunks i–j, chars a–b)` provenance). `_evidence_texts` now mirrors `_build_source_content` exactly — it uses the same `select_chunks`/`render_chunk_evidence` seam for documents with chunks, falling back to whole extracted text otherwise — so **claim verification checks the answer against the same evidence the prompt carried**, including chunk spans. The verifier never re-introduces whole-document assumptions.

## 5. Behavior (validated)

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

**Conversation-history protection:** history is demoted to non-citable context (instruction) AND cannot satisfy the verbatim/acronym checks (deterministic) — a claim sourced only from history fails verification.

**Citation behavior:** supported claims keep their citation (`[1] Cblu Jan, 2024.pdf`); refused claims carry **no citations**.

**Provenance behavior:** the evidence seam carries chunk index range + character spans; `document_id`/chunk provenance flows unchanged through retrieval, evidence assembly, and now the verifier.

## 6. Test results

| Suite | Result |
|---|---|
| `test_claim_support.py` | **26 passed** |
| `test_evidence_contract.py` | **16 passed** |
| `test_chunk_evidence_path.py` | **7 passed** |
| Combined focused + P1 + retrieval regression | **206 passed** |
| **Full backend** | **1,849 passed, 2 skipped** (9 pre-existing Qdrant env failures + 1 pre-existing flaky intake timing test — both untouched, classified earlier) |
| Frontend / typecheck | unchanged (no frontend change; previously 101 passed / 0 errors) |
| `git diff --check` | clean |

## 7. Known limitations

1. The verifier is **deterministic** (verbatim containment + acronym guard in extraction mode; content-token coverage flag in general mode). A semantic LLM-judge for claim-level support remains a later-phase extension — deliberately not added here.
2. General-mode `claim_supported` is an advisory coverage flag, not a refusal trigger (refusal is extraction-mode only — by design).
3. The 22–43 ms pathological common-term retrieval benchmark at 10k docs remains documented and unchanged (P2 decision, not touched by this patch).
4. PG runtime benchmarking of the FTS path still requires your local PostgreSQL (not available in the sandbox).

## 8. ZIP contents (repository-relative)

- `backend/app/application/assistant/claim_support.py`
- `backend/app/application/dtos/ai.py`
- `backend/app/application/use_cases/ai/grounded_qa.py`
- `backend/app/tests/unit/test_claim_support.py`
- `backend/app/tests/unit/test_evidence_contract.py`
- `backend/app/tests/integration/test_chunk_evidence_path.py`
- `APPLY_STEPS.md`, `CHANGE_REPORT.md`

No migration required. Rollback: see APPLY_STEPS §9 (timestamped backup + restore).
