# Root Cause & Fix Report

## A. Root cause of the 404

The `/ai/chat` endpoint EXISTS and is correctly registered. It returns HTTP 404
because `AI_CHAT_ENABLED` defaults to `false` in `backend/app/core/config.py`.
All AcademicOS AI endpoints are feature-flagged (default OFF) and return 404
when their flag is not enabled.

The user's backend `.env` file did not contain `AI_CHAT_ENABLED=true`, so the
endpoint correctly returned 404 — this is the intended behavior, not a bug.

## B. Files changed (3 code + 1 config)

| File | Why |
|---|---|
| `frontend/src/app/(main)/chat/page.tsx` | Detect HTTP 404 from feature gate and show actionable message: "Add AI_CHAT_ENABLED=true to the backend .env" |
| `frontend/src/components/layout/Sidebar.tsx` | "AI Chat" nav link (from M21) |
| `frontend/src/lib/api/ai.ts` | `aiChat()`, `summarizeDocument()`, `enrichDocument()` client functions (from M21) |
| `frontend/src/types/index.ts` | AI response types (from M21) |
| `backend/.env.example` | Added ALL AI feature flags so they're discoverable; `AI_CHAT_ENABLED=true` pre-set in the template |

## C. What the user must do

Add `AI_CHAT_ENABLED=true` to `backend/.env` (the real env file, not .env.example).
If using a local/free model (Ollama etc.), also set `AI_PROVIDERS_JSON`.

## D. Complete test results
- Frontend Vitest: 76 passed (16 files)
- Frontend build: success
- TypeScript: exit 0
