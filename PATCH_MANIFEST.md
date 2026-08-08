# AcademicOS M15 — Incremental Patch Manifest (AI Chat over All Documents — F17)

**Parent commit:** `bfa0124` (M14.1) · **Commit:** `bb561d3` · **Date:** 2026-08-08
**Scope:** F17 AI Chat — conversational, document-grounded chat. Reuse-only; no new abstractions.

## Files Added
| Path | Purpose |
|---|---|
| `backend/app/application/use_cases/ai/chat.py` | `ChatUseCase` (composes `GroundedQAUseCase`, synthesizes conversation from client history), `ChatTurn`, `CHAT_SYSTEM_INSTRUCTIONS`. |
| `backend/app/tests/unit/test_chat.py` | 9 unit tests: history reaches prompt, grounding preserved, chat instructions, history cap, leak-proof streaming (success/failure/incomplete), fallback, real provenance. |
| `backend/app/tests/integration/test_ai_chat_api.py` | 8 integration tests: flag off (404), master switch off (404), auth (401), validation (422 ×2), empty/turns history accepted, streaming gate. |

## Files Modified
| Path | Change |
|---|---|
| `backend/app/application/use_cases/ai/grounded_qa.py` | Additive optional `conversation` param on `execute`/`stream`/`_prepare`; `context_builder.build(conversation, …)`. QA unchanged when `conversation=None` (preserved — QA tests green). |
| `backend/app/api/routes/ai.py` | `POST /ai/chat` + `POST /ai/chat/stream`; `ChatBody`/`ChatMessageModel`/`ChatResponseModel`; `_build_chat_use_case` helper (gate → resolve embedder/vector → compose engine with chat instructions). |

## Reuse map (constraints honoured)
- `GroundedQAUseCase` (the grounded-generation engine) — generalized additively, not duplicated.
- `AssistantRetrievalService` (permission-filtered) · `AssistantContextBuilder` (reads `msg.<seq>` history) · `AssistantPromptBuilder` · `CitationBuilder` · `AnswerVerifier` · `DocumentAnnotationService` (authoritative source text) · `LanguageModelGateway.generate/stream` · `append_message` (history synthesis) · M13.1 provenance · M13.1.1 leak-proof streaming.
- No new provider/embedder/vector/transport owner/AI Core/persistence/prompt framework. AiCore remains configuration authority. Application framework-free guardrail holds (`chat.py` imports only stdlib + app.application/app.domain). M11/M12/M13/M14 behaviour preserved (architecture 16/16).

## Verification
- Backend: **1560 passed, 2 skipped** (+17 new; zero regressions)
- Architecture guardrails: **16/16** · ruff clean
- Frontend Vitest: **76 passed** · `tsc --noEmit` exit 0 (backend-only — unaffected)
