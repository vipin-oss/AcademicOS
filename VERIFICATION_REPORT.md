# Verification Report — Sprint M15 (AI Chat over All Documents — F17)

**Parent commit:** `bfa0124` (M14.1) · **Commit:** `bb561d3` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** F17 AI Chat.

---

## 1. Capability & roadmap evidence
`AcademicOS_AI_Architecture.md` **Appendix F.1 — Phased Build Sequence** defines P3 (Retrieval & Reasoning) = F13–F17 with exit criteria "Search p95 ≤ 300 ms; QA hallucination ≤ 1.5%; Chat scope adherence 100%". F13 Semantic Search, F14 QA, F15 Summarization, F16 Related were delivered in M12–M13.3. **F17 — AI Chat over All Documents is the last unfinished P3 item**, behind the existing `ai_chat_enabled` flag (M11.1). Group C capability ordering confirms (#17 follows the implemented #13–16). No roadmap redesign.

## 2. Root design (reuse-only)
Conversational, document-grounded chat. The latest message is grounded in the caller's readable documents exactly like grounded QA, **and** the prompt carries client-supplied conversation history (stateless server; persistence deferred to M14+).

The entire grounded-generation pipeline is the existing `GroundedQAUseCase`, generalized with an **additive optional `conversation`** parameter (QA single-turn behaviour preserved when `None`). `ChatUseCase` composes it and only:
- synthesizes a transient conversation from client history via the existing `append_message` helper (read as `msg.<seq>` history by the existing `AssistantContextBuilder`);
- supplies chat-specific system instructions (conversational + grounded).

No pipeline duplication, no new abstraction.

## 3. Contract verification

| Requirement | Result |
|---|---|
| Feature flag OFF → 404 (no embedder/vector touch) | ✅ `test_chat_404_when_flag_off`, streaming gate |
| AI master switch OFF + flag ON → 404 | ✅ `test_master_switch_off_blocks_even_when_flag_on` |
| Authentication | ✅ `test_chat_requires_auth` (401) |
| Valid success (history + grounding) | ✅ `test_history_reaches_prompt` (prior turns + source text in prompt) |
| Empty/missing input | ✅ missing message → 422; empty history accepted (200) |
| Malformed input | ✅ unknown field → 422 |
| Infrastructure/provider failure | ✅ `test_gateway_failure_returns_honest_fallback` (available=False) |
| Streaming — no partial output before completion | ✅ `test_success_flushes_tokens_then_completion`, `test_failure_leaks_no_tokens`, `test_incomplete_stream_is_failure` |
| Provenance (real, not fabricated) | ✅ `test_success_provenance_is_real` (provider/model/prompt-id/tokens/latency from the result) |
| Boundary/limit | ✅ `test_only_newest_history_turns_kept` (history cap = 20) |
| Permission (no unauthorized docs) | ✅ inherited from permission-filtered retrieval (unchanged) |
| Existing-functionality regression | ✅ QA tests green (additive generalization); full suite 1560 |

## 4. Independent audit

| # | Check | Result |
|---|---|---|
| 1 | Feature gate before feature-specific deps | ✅ gate raises 404 before `_build_chat_use_case` resolves embedder/vector |
| 2 | Permission boundaries | ✅ retrieval permission-filtered; no unauthorized objects returned |
| 3 | Data leakage | ✅ none (answer + verified citations only) |
| 4 | Error handling / fallback | ✅ gateway failure → available=False |
| 5 | Provenance | ✅ real GenerationResult; prompt_id from builder |
| 6 | Streaming | ✅ leak-proof (inherited from M13.1.1) |
| 7 | Race conditions / stale state | ✅ n/a (backend-only; stateless) |
| 8 | Duplicate infrastructure | ✅ none (composes GroundedQAUseCase) |
| 9 | Dead code / debug / secrets | ✅ none |
| 10 | Backward compatibility | ✅ QA additive (conversation=None default); M11–M14 preserved |
| 11 | Architecture boundaries | ✅ `chat.py` framework-free; 16/16 guardrails |

**Findings:** Production-critical: **0**. Non-critical: **0**. (Stateless chat by design — server-side conversation persistence is a deferred M14+ item, not a defect.)

## 5. Test execution (actual)

| Suite | Result |
|---|---|
| M15 targeted (chat unit + integration + config + architecture + QA) | **51 passed** |
| Backend full suite | **1560 passed, 2 skipped, 0 failed** (1543 → 1560; +17) |
| Architecture guardrails | **16/16** |
| Frontend Vitest | **76 passed** (backend-only — unaffected) |
| TypeScript `tsc --noEmit` | **exit 0** |
| Ruff (changed files) | clean (only accepted `B008`/`E402`) |
| Boot/import | **271 routes** (`/ai/chat` + `/ai/chat/stream` registered) |

## 6. Repository integrity
- Changed: `chat.py` (new), `grounded_qa.py` (additive), `ai.py` (routes+models), `test_chat.py` (new), `test_ai_chat_api.py` (new). **No config changes** (flag pre-existing). No unrelated files, no debug code, no secrets, no dead code.
- Working tree clean after commit; branch `feature/m11-ai-workspace`.

## 7. Deliverables
- **Patch ZIP:** `releases/m15/m15-patch.zip`
- **Patch diff:** `releases/m15/m15.patch` (parent `bfa0124` → `bb561d3`)
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M15 entry prepended)
