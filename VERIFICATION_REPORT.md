# Verification Report — Sprint M13.1.1 (Corrective — QA Defect Fixes)

**Baseline:** `4f079a8` (M13.1) · **Commit:** `ae55aeb` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** corrective only.

---

## 1. Defect-1 — Streaming QA leaks partial answers

### Root cause
`GroundedQAUseCase.stream()` yielded `{"type": "token", ...}` events *immediately*
as each chunk arrived. Two contract violations followed:
1. A gateway failure after some tokens had been emitted returned an
   `available=False` completion — but the partial answer had already leaked.
2. A stream that terminated **without** a `complete` event fell through to a
   post-loop branch that assembled the buffered chunks and returned them as a
   successful (`available=True`) result.

### Fix
Tokens are now **buffered** during iteration and **flushed only after a
confirmed `complete` event** (in arrival order). A stream that ends without a
`complete` event — or that raises — is a **generation failure**: the buffer is
discarded and the shared honest `available=False` fallback is yielded. No token
event is emitted until success is confirmed. The streaming fallback reuses the
**same** `_fallback()` helper as synchronous QA, so both report an identical
honesty contract.

### Regression tests (`TestStreamingLeak`, 4)
| Test | Asserts |
|---|---|
| `test_successful_stream_emits_tokens_then_completion` | Success → token events (in order) THEN one `available=True` completion. |
| `test_gateway_failure_mid_stream_leaks_no_tokens` | Raise after 2 tokens → **no token events**, single `available=False` fallback. |
| `test_stream_without_completion_event_is_generation_failure` | Stream ends with no completion → **no token events**, single `available=False`. |
| `test_streaming_fallback_matches_sync_honesty_contract` | Sync + streaming fallback return identical `available=False` + identical message. |

---

## 2. Defect-2 — QA is not actually grounded

### Root cause
The grounded context rendered only `RetrievedItem` metadata
(`title`, `object_id`, `version`, `sources`, `score`). No document content or
search passages reached the model, so it answered from titles, not evidence.

### Fix
For each retrieved item, the use case now loads its **authoritative extracted
text** through the **existing** intake-extraction pipeline
(`DocumentAnnotationService.extracted_text` → `GetIntakeExtractedTextUseCase`
— the same source the document viewer and summarization consume) and injects
it into the generation prompt as a delimited, untrusted `SOURCE CONTENT`
section. Each passage is marked with the **same** citation number that appears
in the `RETRIEVED CONTEXT` section (`citations[index].number`), so the model
can cite it. Missing text (non-documents, un-extracted items) is skipped —
non-fatal. Per-item text exceeding the budget is truncated and disclosed via
the `truncated` flag. **No new retrieval pipeline; `AssistantContextBuilder`
and `AssistantPromptBuilder` are reused unchanged** — only the QA use case
enriches the prompt it owns.

### Regression tests (`TestGrounding`, 5)
| Test | Asserts |
|---|---|
| `test_authoritative_source_text_reaches_prompt` | Both documents' real content + `<<<SOURCE TEXT>>>`/`<<<END>>>` delimiters present; intake pipeline was the source. |
| `test_each_passage_carries_its_citation_number` | Passage block is `[1] <title>\n<<<SOURCE TEXT>>>\n<text>` (citeable). |
| `test_missing_text_is_skipped_not_fatal` | Item without text produces no empty passage block; present items still injected. |
| `test_long_source_text_truncated_and_disclosed` | 5000-char passage capped to `_MAX_SOURCE_CHARS_PER_ITEM`; `truncated=True`. |
| `test_no_annotation_service_keeps_backward_compatible_prompt` | Without the text source the prompt is the pre-fix envelope (no `SOURCE CONTENT`). |

---

## 3. Defect-3 — Provenance reports the wrong prompt identity

### Root cause
`QAResult.prompt_id` was hardcoded to `"ai.grounded_qa"` (6 sites), but the
generated prompt is produced by `AssistantPromptBuilder` without a registry, so
its true identity is `assistant.default` (`DEFAULT_PROMPT_ID`), version 1.

### Fix
Provenance now carries `prompt.prompt_id` / `prompt.prompt_version` — the
values **actually produced by the prompt builder** — via the shared
`_success_result()` and `_fallback()` helpers. The hardcoded
`_QA_PROMPT_ID` / `_QA_PROMPT_VERSION` constants are removed. All four paths
(sync success, sync fallback, streaming success, streaming fallback) report a
consistent identity.

### Regression tests (`TestProvenance`, 4)
| Test | Asserts |
|---|---|
| `test_success_reports_builder_prompt_id_not_hardcoded` | `prompt_id == "assistant.default"`, `prompt_version == 1`, `!= "ai.grounded_qa"`. |
| `test_sync_fallback_reports_consistent_provenance` | Sync fallback reports `assistant.default`. |
| `test_streaming_success_reports_consistent_provenance` | Streaming success reports `assistant.default`. |
| `test_streaming_fallback_reports_consistent_provenance` | Streaming fallback reports `assistant.default`. |

---

## 4. Test execution

### 4.1 Targeted QA tests
```
$ python -m pytest app/tests/unit/test_grounded_qa.py app/tests/integration/test_ai_qa_api.py -q
..................                                                       [100%]
18 passed in 3.16s
```

### 4.2 Architecture guardrails
```
$ python -m pytest app/tests/architecture/ -q
................                                                         [100%]
16 passed in 3.71s
```

### 4.3 Full backend regression
```
$ python -m pytest app/tests/ -q
1462 passed, 2 skipped in 304.85s
```
Baseline 1444 → **1462** (+13 new regression tests, 2 pre-existing skips, **0 failures**).

### 4.4 Frontend regression (unaffected)
Backend-only change with an unchanged `QAResult` shape; the frontend has no
QA / `prompt_id` references. Confirmed:
```
$ npx vitest run
Test Files  15 passed (15)
     Tests  70 passed (70)
```

### 4.5 Lint
```
$ ruff check app/application/use_cases/ai/grounded_qa.py app/tests/unit/test_grounded_qa.py
All checks passed!
```
(`ai.py` carries only the pre-existing FastAPI `B008 Depends()` idiom shared by
every route, including the existing summarize route — not introduced here.)

---

## 5. Constraints honoured

| Constraint | Status |
|---|---|
| No scope expansion / new features | ✓ only the three defects + a latent double-verify bug |
| Reuse existing M11/M12 components | ✓ `DocumentAnnotationService`, intake pipeline, all assistant builders |
| AI Core = single composition authority | ✓ unchanged |
| Transport ownership | ✓ httpx isolation guardrail passes |
| Architecture guardrails | ✓ 16/16 |
| Backward compatibility | ✓ `QAResult` shape unchanged; annotation/storage optional on the use case |
| No new abstractions / endpoints / flags / persistence | ✓ |

## 6. Deliverables
- **Patch ZIP:** `releases/m13.1.1/m13.1.1-patch.zip`
- **Patch diff:** `releases/m13.1.1/m13.1.1.patch`
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M13.1.1 entry prepended)
