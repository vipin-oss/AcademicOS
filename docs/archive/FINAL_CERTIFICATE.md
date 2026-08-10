> **ARCHIVED — historical record.** This document describes the "Sprint 8 / M8"
> release state (commit `80892d6`). It is preserved for history only and does
> NOT describe the current branch (`feature/m11-ai-workspace`, HEAD `26c5f80`
> and later, which ships M10–M25 incl. AI chat, semantic search, and domain
> assistants). See `README.md` and `CHANGELOG.md` for the current state.

# AcademicOS — Final Release Certificate

**Release:** 1.0.0 — Sprint 8 complete
**Git commit:** `80892d6`
**Date:** 2026-08-07
**Signed by:** AcademicOS Release Engineering (automated verification)

---

| Requirement | Status | Evidence |
|---|---|---|
| Backend verified | ✅ | 1209 passed / 2 skipped; boots; 252 routes; ruff + guardrails clean |
| Frontend verified | ✅ | 35 vitest passed; `tsc --noEmit` 0 errors; `next build` 0 export errors |
| Database verified | ✅ | Migrations 0001→0007; `init_db.py` creates + stamps fresh SQLite; PostgreSQL path via docker-compose + alembic |
| Authentication verified | ✅ | register → login → me → protected API → refresh → forgot → reset, exercised live over HTTP; CORS preflights 200 |
| Build verified | ✅ | Production build compiles; `next start` serves every route |
| Runtime verified | ✅ | Backend + frontend running concurrently; 16/16 protected pages serve 200 with a session |
| Fresh installation verified | ✅ | Zero-infrastructure SQLite quickstart executed on a fresh database; full-stack path documented and tested at the migration level |
| Localhost verified | ✅ | `127.0.0.1:3000` (and `localhost`, `[::1]`) CORS-allowed; frontend default API is the IPv4 literal `127.0.0.1:8000` |
| Ready for development | ✅ | See INSTALL.md — extract, install, run, register, sign in |

---

**Certified:** this release is complete, internally consistent, and
functional on a fresh machine. Extract the release ZIP, follow
`INSTALL.md`, and the application runs end-to-end.

*AcademicOS Release Engineering*
