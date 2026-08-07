# AcademicOS M10 Release Candidate 1 — Incremental Patch Manifest

**Milestone:** M10 RC1 (production release candidate — feature-frozen)
**Baseline:** `f891383` (audited M10 HEAD, verified identical tree to local `25e487c`)
**Patch commits:** `7b3c019` (backend upload cap) · `c16e90d` (frontend authenticated downloads) · `5f149b5` (Windows automation hardening) · `1213b3a` (literal-path patch application) · docs on top
**Date:** 2026-08-07

This patch contains ONLY the M10 release review's production hardening —
no new functionality, no architectural changes, no new dependencies.
Apply it over any M10 installation (M10 Complete → Final Polish → this).
Fully backward compatible: nothing is removed or renamed.

---

## Files Modified

| Path | Change |
|---|---|
| `backend/app/api/routes/documents.py` | Uploads capped at the shared 512 MB limit (`MAX_FILE_BYTES`): declared-size fast path + chunked read, both rejecting oversize with **413** (was an unbounded in-memory read) |
| `backend/app/tests/integration/test_documents_api.py` | `test_upload_rejects_oversized_files` (HTTP 413) + `test_read_upload_size_cap` (helper unit check) |
| `frontend/src/hooks/useObjects.ts` | Removed leftover debug `console.log` |
| `frontend/src/lib/documents/download.ts` | `downloadDocument` now takes the structural `DownloadableDocument` (`{id, file_name?, title?}`) instead of the full response |
| `frontend/src/lib/documents/constants.ts` | Added `MAX_UPLOAD_BYTES` (512 MB, mirrors backend) |
| `frontend/src/app/(main)/documents/[id]/page.tsx` | Download action → authenticated `useDocumentDownload` button (was a raw `<a href>` that 401'd); errors surface via toast |
| `frontend/src/components/features/documents/DocumentCard.tsx` | Download action → authenticated button with busy/error state (was a raw `<a href>`) |
| `frontend/src/components/features/documents/DocumentRow.tsx` | Same as `DocumentCard` (row click-through preserved via stopPropagation) |
| `frontend/src/components/features/documents/DocumentPreview.tsx` | Download action → authenticated button; failures render a `role="alert"` (was a raw `<a href>` fallback) |
| `frontend/src/components/features/documents/DocumentPreview.test.tsx` | Pins the authenticated download + failure surfacing |
| `frontend/src/components/features/documents/ImageViewer.tsx` | Dropped the unsound `as never` cast (structural type now satisfies the helper) |
| `frontend/src/components/features/documents/UploadModal.tsx` | Client-side 512 MB pre-check before starting the transfer |
| `apply_patch.ps1` | Root launcher made ASCII-safe (em-dashes removed) |
| `start.ps1` | Root launcher made ASCII-safe |
| `stop.ps1` | Root launcher made ASCII-safe |
| `health.ps1` | Root launcher made ASCII-safe |
| `scripts/windows/start_academicos.ps1` | Portable temp root (`GetTempPath()`); final summary reports real PostgreSQL/Docker/Qdrant state instead of unconditional green; literal-path file checks |
| `scripts/windows/reset_academicos.ps1` | Literal-path file operations |
| `scripts/windows/validate_environment.ps1` | Literal-path file checks |
| `scripts/windows/health_check.ps1` | Alembic head check matches the `(head)` marker (no hardcoded revision); literal-path file checks |
| `scripts/windows/apply_patch.ps1` | Deleted files backed up; single wrapper folder stripped so wrapped/flat zips apply identically; identical files skipped (idempotent re-apply reports 0/0); `PATCH_MANIFEST.md` installed with the patch; **all file operations use `-LiteralPath`** — PowerShell treats `[` `]` in `-Path` as wildcards, which silently skipped Next.js dynamic-route files (`documents/[id]/page.tsx`, …); directory creation via `[System.IO.Directory]::CreateDirectory` (`New-Item` has no `-LiteralPath`) |
| `CHANGELOG.md` | M10 RC1 entry |
| `README.md` | Migration count corrected to `0001..0008`; RC1 note |

## Files Added

| Path | Purpose |
|---|---|
| `frontend/src/hooks/useDocumentDownload.ts` | Shared authenticated-download hook (busy id + error state, no swallowed failures) |
| `FINAL_RELEASE_NOTES.md` | Official M10 RC1 release notes |

## Files Deleted

*(none)*

## Database Migrations

*(none)* — no schema change.

## New Dependencies

*(none)* — `jszip@3.10.1` arrived with M10 Final Polish and is already in `package.json`.

## Environment Variable Changes

*(none)*

## Post-Apply Commands

```powershell
# Nothing schema- or dependency-related. Restart the services:
.\stop.ps1
.\start.ps1
```

Or, if the backend/frontend are running, just restart them:

```powershell
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

## Verification (this patch)

- Backend: **1242 passed, 2 skipped** (2 skips = PostgreSQL-gated JSONB containment)
- Frontend: **65 passed (14 files)**; `tsc --noEmit` clean; `next build` clean
- Architecture guardrails: 7/7
- Windows scripts: AST parse clean (PowerShell 7 parser, PS 5.1-compatible syntax); ASCII-safe;
  `apply_patch.ps1` functionally verified end-to-end (apply → re-apply idempotent, backups, wrapper strip)
- Manual API: upload 201 / oversize 413 / download 200 with JWT / 401 without
