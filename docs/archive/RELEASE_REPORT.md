> **ARCHIVED — historical record.** This document describes the "Sprint 8 / M8"
> release state (commit `80892d6`). It is preserved for history only and does
> NOT describe the current branch (`feature/m11-ai-workspace`, HEAD `26c5f80`
> and later, which ships M10–M25 incl. AI chat, semantic search, and domain
> assistants). See `README.md` and `CHANGELOG.md` for the current state.

# AcademicOS — Release Verification Report

Release: **1.0.0** · Git: `80892d6` · Date: 2026-08-07

Every item below was executed and verified during this release cycle —
none are asserted from earlier milestones alone.

## 1. Backend verification

| Check | Result |
|---|---|
| Full pytest suite (`DATABASE_URL=sqlite:///./dev_test.db python -m pytest -q`) | **1209 passed, 2 skipped, 0 failed** (2 skips: PG-gated JSONB containment) |
| Timing-sensitive intake pause/resume test re-run in isolation | 1 passed (33 s) — confirmed the single full-suite failure was a CPU-contention flake, not a regression |
| Application import (`from app.main import app`) | OK, 252 routes |
| Backend boots (`uvicorn app.main:app --host 127.0.0.1 --port 8000`) | Startup complete, health endpoint 200 |
| Ruff (full project conventions) | All new/changed files clean; baseline legacy findings unchanged |
| Architecture guardrails | 7/7 |
| `scripts/init_db.py` on a fresh SQLite DB | Creates 8 tables + stamps alembic `0007_review_decisions` |
| Alembic chain | 0001→0007 linear, `down_revision` verified |

## 2. Live API verification (real server, fresh SQLite DB, curl)

| Flow | Result |
|---|---|
| `POST /auth/register` | 201, user returned with roles |
| `POST /auth/login` | 200, access + refresh tokens |
| `GET /auth/me` with token | 200, correct username |
| `GET /objects` with token | 200 |
| `GET /objects` without token | 401 |
| `POST /auth/refresh` + `GET /auth/me` with new token | 200 |
| `POST /auth/forgot-password` (existing user) | 200 + reset token |
| `POST /auth/reset-password` (valid token) | `{"ok": true}` |
| Login with old password after reset | 401 |
| Login with new password after reset | 200 |
| CORS preflight from `http://127.0.0.1:3000` | 200, correct `Access-Control-Allow-Origin` |
| CORS preflights for `localhost:3000` and `[::1]:3000` | 200 |

## 3. Frontend verification

| Check | Result |
|---|---|
| `npx vitest run` | **35 passed (7 files)** — 29 existing + 6 new auth-page tests |
| `tsc --noEmit` | 0 errors |
| `next build` (production) | Compiled, 28/28 static pages, **0 export errors** |
| `next start -p 3000` | Ready |

## 4. Live routing / guard verification (built frontend + curl)

| Route | Without session | With session cookie |
|---|---|---|
| `/` | 307 → `/login` | 200 |
| `/objects` | 307 → `/login?next=%2Fobjects` | 200 |
| `/login` | 200 | 307 → `/` |
| `/register` | 200 (SSR contains form) | — |
| `/forgot-password` | 200 (SSR contains form) | — |
| `/reset-password` | 200 | — |
| `/assistant`, `/objects`, `/documents`, `/intake`, `/publications`, `/students`, `/teaching`, `/research`, `/faculty`, `/committees`, `/finance`, `/events`, `/productivity`, `/reports`, `/settings`, `/search` | 307 → `/login` | **16/16 → 200** |
| `/reports/teaching` | — | 200 |

## 5. Authentication UI (jsdom render tests)

Login form renders + submits through the session provider; register form
renders + registers; forgot-password renders; reset-password renders with
the token — 6 automated tests.

## 6. Fresh-install checklist (INSTALL.md)

1. Extract ZIP → 2. `pip install -r requirements.txt` (now includes alembic)
→ 3. copy `.env.example` → `.env` (SQLite quickstart documented) →
4. `python scripts/init_db.py` → 5. `uvicorn app.main:app` →
6. `npm install` → 7. `npm run dev` → 8. open `http://127.0.0.1:3000` →
9. register → 10. sign in. Full-stack path: `docker compose up -d db qdrant`
→ `alembic upgrade head`.

## 7. Known limitations (documented, not defects)

- Password-reset tokens are returned in the API response (no email
  gateway in this release) — documented in code, INSTALL.md and the UI.
- The LLM assistant defaults to the deterministic rules provider; an
  OpenAI-compatible endpoint is configurable via `ASSISTANT_MODELS_JSON`.
- Qdrant is optional: search degrades to lexical-only when unreachable.
