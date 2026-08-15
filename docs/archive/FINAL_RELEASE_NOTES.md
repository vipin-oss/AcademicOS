> **ARCHIVED — historical record.** This document describes the "Sprint 8 / M8"
> release state (commit `80892d6`). It is preserved for history only and does
> NOT describe the current branch (`feature/m11-ai-workspace`, HEAD `26c5f80`
> and later, which ships M10–M25 incl. AI chat, semantic search, and domain
> assistants). See `README.md` and `CHANGELOG.md` for the current state.

# AcademicOS — M10 Release Candidate 1 (RC1) Release Notes

**Release:** M10 RC1 · **Date:** 2026-08-07 · **Audited HEAD:** `f891383` · **Status:** Feature-frozen

Sprint M10 (Native Document Workspace + Windows Automation + Final Polish)
passed an independent engineering audit and is hereby frozen. RC1 is the
official release candidate produced from that audited baseline plus a final
release review that fixed only real, low-risk production issues.

---

## 1. Scope of this release

- **Feature set:** everything delivered through Sprint M10, M10.1 and the M10
  Final Polish — the complete Document Workspace (PDF full-text search,
  thumbnails, multi-document tabs, image/office viewers, citations,
  selection actions, KG links, annotations + extracted text), the M9 Commit
  Engine review workflow, and the Windows PowerShell automation suite.
- **RC1 delta (this patch):** production hardening only. No new features, no
  architectural changes, no new dependencies, no schema changes.

## 2. What RC1 fixed

| # | Fix | Class |
|---|---|---|
| 1 | All document download actions now go through the authenticated API client. Four surfaces (detail page, card, row, preview) previously rendered plain `<a href>` links to the API download URL, which cannot carry the JWT — every such click returned **401** in production. A shared `useDocumentDownload` hook provides busy/error state; failures are never swallowed. | Real bug |
| 2 | Document uploads are capped at the intake pipeline's shared **512 MB** limit with a chunked read (413 on oversize). The route previously read the entire request body into memory unbounded — a memory-exhaustion vector on an authenticated endpoint. The upload modal pre-checks the cap client-side. | Production hardening |
| 3 | Removed a leftover debug `console.log` in `useObjects.ts`. | Debug code |
| 4 | Root PowerShell launchers made ASCII-safe (em-dashes removed). Windows PowerShell 5.1 misreads non-BOM UTF-8 and can fail to parse such files. | Windows reliability |
| 5 | `start_academicos.ps1` uses `[IO.Path]::GetTempPath()` for logs (the `TEMP` env var is not guaranteed in every environment) and its final summary now reports the *actual* PostgreSQL / Docker / Qdrant state instead of unconditional green `[OK]` lines. | Windows reliability |
| 6 | `health_check.ps1` Alembic check matches the `(head)` marker instead of a hardcoded revision — future migrations cannot silently break the health check. | Windows reliability |
| 7 | `apply_patch.ps1`: deleted files are now backed up; a single wrapper folder in a patch ZIP is stripped so wrapped and flat archives apply identically (previously mis-applied); re-applying a patch now reports 0 Added / 0 Modified as documented (verified end-to-end). | Windows reliability |
| 8 | **Literal-path file operations** (all Windows scripts): PowerShell treats `[` `]` in `-Path` as wildcard classes, so files under Next.js dynamic-route segments (`documents/[id]/page.tsx`, `objects/[id]/page.tsx`, …) were silently skipped by the patcher — counted as added while keeping old content. Every file operation now uses `-LiteralPath`; directory creation uses `[System.IO.Directory]::CreateDirectory` (`New-Item` has no `-LiteralPath`). Caught by applying the RC1 patch to a clean `f891383` checkout: the resulting tree is now **byte-identical** to RC1 HEAD. | Windows reliability |
| 9 | Documentation: `README.md` migration count corrected to `0001..0008`; `FINAL_RELEASE_NOTES.md` added. | Docs |

## 3. Verification (full suite, 2026-08-07)

| Gate | Result |
|---|---|
| Backend test suite | **1242 passed, 2 skipped** (2 skips = PostgreSQL-gated JSONB containment; was 1240 + 2 new RC1 tests) |
| Frontend tests | **65 passed (14 files)** (was 64) |
| TypeScript | `tsc --noEmit` — clean |
| Production build | `next build` — clean (0 export errors) |
| Architecture guardrails | **7/7** |
| Migrations | Alembic chain `0001…0008` intact; SQLite init idempotent (stamped at `0008_document_annotations`) |
| Windows scripts | All 10 `.ps1` files AST-parse clean (PowerShell 7.4 parser — PS 5.1-compatible grammar), ASCII-safe; `apply_patch.ps1` functionally exercised: first apply / idempotent re-apply 0/0/0/0, wrapped and flat ZIP layouts identical, `[id]`-style bracket paths replace correctly; **the RC1 patch applied to a clean `f891383` checkout reproduces RC1 HEAD byte-for-byte (0 diff lines)** |
| Manual API | Register/login → upload 201 → oversize 413 → download 200 (JWT) → 401 without JWT → annotations CRUD 200/204 → extracted-text 200 |

## 4. Backward compatibility

- No API contract changes: same routes, same request/response shapes.
- No database migrations in this patch.
- No new dependencies.
- Existing installations upgrade by applying `AcademicOS_M10_RC1_Patch.zip`
  (see `PATCH_MANIFEST.md`), then restarting the services.

## 5. Windows automation (one-command developer experience)

`.\\start.ps1`, `.\\stop.ps1`, `.\\health.ps1`, `.\\apply_patch.ps1
<your_patch.zip>`, plus `scripts\\windows\\reset_academicos.ps1` and
`validate_environment.ps1` — PowerShell 5.1+ / 7, Windows 10/11, ASCII-safe,
idempotent, with proper exit codes. PostgreSQL is never touched by stop/reset.

## 6. Known limitations (deliberately deferred — Sprint M11 or later)

Per the audit and the feature freeze, the following are **not** part of M10
and were intentionally not implemented: continuous scroll, PDF text layer,
async SQLAlchemy, API rate limiting, dark mode, fullscreen/print modes,
annotation editing, Playwright test tooling, CI pipelines, Drive/OneDrive
activation, tenancy, and i18n completion.

## 7. Release sign-off

- Independent audit: **PASSED** — M10 may be frozen (only non-blocking
  improvements remained; none became scope creep).
- RC1 release review: **COMPLETE** — every fix above satisfies all of:
  real bug, production-quality improvement, low risk, no architectural
  rewrite, no feature creep.
- Verification: **FULL SUITE GREEN** (backend 1242/2, frontend 65, tsc,
  next build, guardrails 7/7, migrations, Windows scripts, manual API).

**M10 Release Candidate 1 is production-ready and recommended for release.**

After RC1, M10 is frozen permanently. All remaining improvements are
scheduled for Sprint M11 or later.
