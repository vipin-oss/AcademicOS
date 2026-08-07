# AcademicOS — Final Release Changelog

Release: **1.0.0 (Sprint 8 complete)** · Git: `80892d6` · Date: 2026-08-07

This release closes the gaps found by the forensic audit: the frontend is
now fully functional end-to-end (authentication, route guards, session
management), previously backend-only surfaces are wired into the UI, all
placeholder modules are removed, and fresh-machine bring-up is documented
and verified.

## Authentication (new)

| File | Change |
|---|---|
| `backend/app/api/routes/auth.py` | Added `POST /auth/forgot-password` and `POST /auth/reset-password` |
| `backend/app/application/use_cases/auth/forgot_password.py` | **new** — enumeration-safe reset-token issuance |
| `backend/app/application/use_cases/auth/reset_password.py` | **new** — token-gated password change |
| `backend/app/application/commands/forgot_password.py` | **new** — CQRS command |
| `backend/app/application/commands/reset_password.py` | **new** — CQRS command |
| `backend/app/application/dtos/auth.py` | `ForgotPasswordInput/Output`, `ResetPasswordInput` |
| `backend/app/application/validators/auth.py` | Reset input validation (reuses password rules) |
| `backend/app/application/ports/token_service.py` | `create_reset_token` |
| `backend/app/infrastructure/auth/jwt.py` | `create_reset_token` (type=reset, 30 min TTL) |
| `backend/app/infrastructure/auth/jwt_service.py` | Adapter implements the new port verb |
| `backend/app/core/config.py` | `password_reset_token_ttl_seconds` (default 1800) |
| `backend/app/tests/integration/test_auth_api.py` | +4 reset-flow integration tests |

## Frontend authentication stack (new)

| File | Change |
|---|---|
| `frontend/src/app/(auth)/login/page.tsx` | **new** — login form (Suspense + force-dynamic) |
| `frontend/src/app/(auth)/register/page.tsx` | **new** — registration form |
| `frontend/src/app/(auth)/forgot-password/page.tsx` | **new** — reset-token request (dev transport) |
| `frontend/src/app/(auth)/reset-password/page.tsx` | **new** — token + new password form |
| `frontend/src/components/features/auth/AuthShell.tsx` | **new** — shared shell + form primitives |
| `frontend/src/lib/auth/session.tsx` | **new** — `AuthProvider`/`useAuth`: auto-login, auto-logout, profile load, login/register/logout |
| `frontend/src/lib/auth/token.ts` | Access+refresh storage, session cookie mirror |
| `frontend/src/lib/api/auth.ts` | **new** — register/login/refresh/me/forgot/reset client |
| `frontend/src/lib/api/client.ts` | Single-flight silent refresh on 401 (auth paths excluded) |
| `frontend/src/middleware.ts` | **new** — route guards (protected → `/login?next=`, auth pages → `/`) |
| `frontend/src/app/(main)/layout.tsx` | **new** — client-side session guard |
| `frontend/src/app/layout.tsx` | Wraps the app in `AuthProvider` |
| `frontend/src/components/layout/TopHeader.tsx` | Signed-in user + sign-out |
| `frontend/src/types/index.ts` | `AuthTokens`, `AuthUser`, `ForgotPasswordResult` |
| `frontend/src/app/(auth)/auth-pages.test.tsx` | **new** — 6 render/submit tests |
| `frontend/package.json` | +`@testing-library/user-event` (dev) |

## Previously backend-only surfaces, now wired

| File | Change |
|---|---|
| `frontend/src/lib/api/objects.ts` | `getObjectGraph`, `getGraphPath`, `getObjectAcl`, `updateObjectAcl` |
| `frontend/src/app/(main)/objects/[id]/page.tsx` | Real Relationships + ACL panels (placeholder removed) |
| `frontend/src/lib/api/assistant.ts` | memory recall/consolidate, review pending/approve/reject, eval history |
| `frontend/src/components/features/assistant/AssistantLabs.tsx` | **new** — Memory / Review queue / Evaluation history tabs |
| `frontend/src/app/(main)/assistant/page.tsx` | Renders Assistant Labs |
| `frontend/src/lib/api/intake.ts` | item proposal, regenerate, commit, commit-preview |

## Placeholders removed

| Path | Action |
|---|---|
| `frontend/src/components/features/{ai-chat,administration,projects}/` | deleted (unreferenced) |
| `frontend/src/components/{common,ui}/`, `frontend/src/lib/storage/`, `frontend/src/{stores,styles}/`, `frontend/src/app/api/`, `frontend/src/lib/utils/` | deleted (unreferenced) |
| All `.gitkeep` files under `frontend/src` | deleted (0 remain) |
| `frontend/public/` | favicon.svg added + linked in root layout |

## Configuration / packaging

| File | Change |
|---|---|
| `backend/requirements.txt` | +`alembic==1.13.2` (migrations were unpinnable) |
| `backend/.env.example` | Documents every setting incl. `assistant_*`, `BOOTSTRAP_ADMIN_USERNAME`, `PASSWORD_RESET_TOKEN_TTL_SECONDS` |
| `backend/scripts/init_db.py` | **new** — SQLite quickstart schema + alembic stamp (idempotent) |
| `frontend/src/config/env.ts` | API default `http://127.0.0.1:8000/api/v1` (Windows IPv4-literal) |
| `frontend/.env.example` | Matched template |
| `docker-compose.yml` | **new** — PostgreSQL 16 + Qdrant for the full stack |
| `INSTALL.md` | **new** — Windows/Linux/macOS installation guide |
| `README.md`, `frontend/README.md` | Rewritten for the released state |

## Defects repaired during release verification

| File | Fix |
|---|---|
| `frontend/src/app/(auth)/login/page.tsx`, `reset-password/page.tsx` | `useSearchParams` wrapped in Suspense + `force-dynamic` (prerender failure) |
| `frontend/src/app/(main)/objects/[id]/page.tsx` | `Section` icon-prop misuse (tsc) |
| `frontend/src/lib/api/intake.ts` | Missing `RequestOptions` import |
