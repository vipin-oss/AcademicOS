# AcademicOS — M10 Release Candidate 1 (RC1) Changelog

Release: **M10 RC1** · Baseline `f891383` (audited M10 HEAD) · Date: 2026-08-07
Status: **feature-frozen; production hardening only — no new functionality**

Sprint M10 passed an independent engineering audit and is frozen. RC1
contains only the release review's low-risk production fixes, verified in
full. All remaining improvements are deferred to Sprint M11 or later.

## Release fixes

| Area | Fix |
|---|---|
| Authenticated downloads | The download endpoints require the bearer token, but the document detail page, `DocumentCard`, `DocumentRow` and `DocumentPreview` rendered plain `<a href={document.url}>` links — an href cannot carry the JWT, so every such click 401'd in production. All four now download through the existing authenticated `downloadDocument` helper via a shared `useDocumentDownload` hook (busy id, no swallowed errors). `downloadDocument` takes the structural `{id, file_name?, title?}` shape, removing the unsound `as never` cast in `ImageViewer` |
| Upload hardening | The document upload route read the whole request body into memory with no cap — an authenticated client could exhaust server RAM. `_read_upload` now enforces the intake pipeline's shared 512 MB cap (`MAX_FILE_BYTES`): a declared-size fast path (where the framework exposes `file.size`) and a chunked read aborting with **413** once the cap is crossed. The upload modal pre-checks the same cap client-side so a doomed transfer never starts |
| Debug code | Removed a leftover `console.log` in `useObjects.ts` |
| Windows launchers | Root `apply_patch.ps1` / `start.ps1` / `stop.ps1` / `health.ps1` still contained em-dashes (the M10.1 polish cleaned `scripts/windows/` but missed the root files); PowerShell 5.1 misreads non-BOM UTF-8 — now ASCII-safe |
| `start_academicos.ps1` | Temp logs now use `[IO.Path]::GetTempPath()` (the `TEMP` env var is not guaranteed in every environment); the final summary reflects the real PostgreSQL / Docker / Qdrant state instead of always printing green `[OK]` |
| `health_check.ps1` | Alembic head check now matches the `(head)` marker Alembic prints instead of a hardcoded `0008`, so future migrations never break the check |
| `apply_patch.ps1` | Deleted files are now backed up like replaced files (they cannot be restored from the patch itself); a single wrapper folder in a patch ZIP is stripped so wrapped and flat archives apply identically (conflict detection and apply previously used the wrong root for wrapped zips); identical files are skipped so re-applying a patch reports **0 Added / 0 Modified** as documented; `PATCH_MANIFEST.md` is installed so the project manifest always reflects the applied state |
| All Windows scripts | **Literal-path file operations** — PowerShell treats `[` `]` in `-Path` as wildcard classes, so Next.js dynamic-route files (`documents/[id]/page.tsx`, `objects/[id]/page.tsx`, …) were **silently skipped** by `apply_patch.ps1` (counted as added, content never replaced). Every `Test-Path` / `Get-Item` / `Get-FileHash` / `Copy-Item` / `Remove-Item` now uses `-LiteralPath`, and directory creation uses `[System.IO.Directory]::CreateDirectory` (`New-Item` has no `-LiteralPath`). Caught by end-to-end verification of the RC1 patch itself against a clean baseline |
| Documentation | `README.md` migration count corrected to `0001..0008`; `FINAL_RELEASE_NOTES.md` added |

## Tests added

- `test_documents_api.py::test_upload_rejects_oversized_files` — HTTP 413 via the chunked read
- `test_documents_api.py::test_read_upload_size_cap` — declared-size fast path, chunked cap, happy path
- `DocumentPreview.test.tsx` — download goes through the authenticated client (no raw href) and failures surface in an alert

## Verification (full suite, 2026-08-07)

- Backend: **1242 passed, 2 skipped** (was 1240 + 2 new cap tests; 2 skips = PostgreSQL-gated JSONB containment)
- Frontend: **65 passed (14 files)** (was 64), `tsc --noEmit` clean, `next build` clean
- Architecture guardrails: **7/7**
- Windows scripts: all 10 parse clean under the PowerShell AST parser; ASCII-safe;
  `apply_patch.ps1` verified end-to-end on PowerShell 7 (apply → re-apply → 0/0/0/0, backups, wrapper-folder strip)
- Manual API verification: upload 201 / oversize 413 / download 200 with JWT / 401 without

---

# AcademicOS — Sprint M10 Final Polish Changelog

Release: **M10 Final Polish** · Baseline `f613b2b` → `HEAD` · Date: 2026-08-07

## Windows automation (audit fixes)

| File | Change |
|---|---|
| `scripts/windows/start_academicos.ps1` | Fixed same-file stdout/stderr redirect bug (separate logs now); fast `TcpClient` port probe replacing slow `Test-NetConnection`; ASCII-safe output |
| `scripts/windows/apply_patch.ps1` | Removed dead backup variable; ASCII-safe output; conflict detection now uses SHA-256 + timestamps consistently |
| `scripts/windows/health_check.ps1` | Fast port probe; DB-file existence check before connecting |
| `scripts/windows/validate_environment.ps1` | Robust Node major-version check (numeric parse); resolves backend dir from any cwd |
| `scripts/windows/stop_academicos.ps1`, `reset_academicos.ps1` | ASCII-safe output |
| All scripts | Unicode (em-dash, ellipsis, checkmarks) removed — ASCII-safe for PS 5.1 on any codepage |

## Frontend fixes

| File | Change |
|---|---|
| `PdfViewer.tsx` | **Controlled page/scale/fitMode props** — the multi-document workspace now genuinely preserves per-tab page/zoom/fit (previously stored but not applied); pdf.js document destroyed on unmount (memory cleanup) |
| `DocumentWorkspace.tsx` | Every tab stays mounted (hidden when inactive) so switching never destroys the pdf and page/zoom/annotations survive; close unmounts → PdfViewer frees the document; fitMode added to tab state |
| `document_viewer` detail page | Live viewer page now drives the CitationPanel page reference (`onPageChange` lifting) |
| `OfficePreview.tsx` + `officeText.ts` | Real DOCX/PPTX/XLSX package parsing with JSZip (readable text/tables/slides) replacing the binary-text approximation; authenticated download fallback (no unauthenticated `<a href>`) |
| `ImageViewer.tsx` | Image error (e.g. TIFF) → inline fallback with authenticated download |
| `KgLinks.tsx` | Fetches the attached AcademicOS object's metadata (committed intake docs) so KG links are populated; document's own object always linked |
| `ExtractedTextPanel.tsx` | Removed duplicate highlight button (SelectionActions owns it); selection preview text |
| `download.ts` | Shared authenticated download helper |

## Tests

- `officeText.test.ts` (5 tests), updated `KgLinks.test.ts`; 64 frontend tests total.

## Verification

- Backend suite: **1240 passed, 2 skipped** (no regressions).
- Frontend: **64 vitest passed**, `tsc --noEmit` clean, `next build` clean.

# AcademicOS — Sprint M10B Changelog (Document Workspace)

Release: **M10B** · Baseline `3f7ed91` (M10A) → `860f2bf` · Date: 2026-08-07

## New features

| Feature | Implementation |
|---|---|
| PDF full-text search | `PdfSearchPanel` (Ctrl+F): match highlighting overlay, Previous/Next, match counter, case-sensitive + whole-word options; pure `searchPdf.ts` matcher (5 tests) |
| Thumbnail sidebar | `ThumbnailSidebar`: lazy-rendered, virtualized page thumbnails, current-page indicator, click-to-jump |
| Multi-document workspace | `DocumentWorkspace` at `/documents/workspace`: tabs, per-tab zoom/page/annotations, close with pdf.js memory cleanup, sessionStorage restore |
| Image viewer | `ImageViewer`: PNG/JPG/JPEG/TIFF/SVG, zoom, pan, fit width/fit screen |
| Office preview | `OfficePreview`: DOCX/PPTX/XLSX read-only browser preview, download fallback |
| Citation workspace | `CitationPanel`: copy citation (academic formatting), page + paragraph references (persistent) |
| AI selection hooks | `SelectionActions`: Explain/Summarize/Rewrite extension points (no fake AI), implemented Highlight/Note/Bookmark |
| Knowledge-graph integration | `KgLinks`: metadata object references → clickable `/objects/{id}` links |
| Accessibility | aria labels, Ctrl+F/Escape/Enter keyboard, focus management, sr-only text |

## Files added
`src/lib/pdf/searchPdf.ts` + test, `PdfSearchPanel.tsx`, `ThumbnailSidebar.tsx`, `DocumentWorkspace.tsx`, `ImageViewer.tsx`, `OfficePreview.tsx`, `CitationPanel.tsx` + test, `SelectionActions.tsx`, `KgLinks.tsx` + test, `src/app/(main)/documents/workspace/page.tsx`, `DocumentViewer.test.tsx` (dispatch).

## Files modified
`DocumentViewer.tsx` (type dispatch), `ExtractedTextPanel.tsx` (selection actions), `PdfViewer.tsx` (search panel + onPdfReady), `documents/[id]/page.tsx` (Citation + KgLinks panels), `src/types/index.ts` (png/jpg/jpeg/tiff/svg), `FileIcon.tsx`.

## Verification
- Backend suite: **1240 passed, 2 skipped** (unchanged — no backend regressions).
- Frontend: **59 vitest passed** (13 new), `tsc --noEmit` clean, `next build` clean.

# AcademicOS — Sprint M10 Changelog

Release: **M10 (Native Document Viewer + Annotation Framework)** · Baseline `c438ff3` → `a3c9935` · Date: 2026-08-07

## Backend — annotations + viewer data

| File | Change |
|---|---|
| `backend/alembic/versions/0008_document_annotations.py` | **new** — `document_annotations` table (annotation_id UUID unique, document_id, type, page, JSONB payload, created_by/at, updated_at; `(document_id, page)` index) |
| `backend/app/infrastructure/db/models/annotation_model.py` | **new** — SQLAlchemy model |
| `backend/app/application/dtos/annotation.py` | **new** — `DocumentAnnotation` record + invariants + factory |
| `backend/app/application/ports/annotation_store.py` | **new** — `AnnotationStore` port (add/get/by_document/update/delete) |
| `backend/app/infrastructure/persistence/annotation_store.py` | **new** — SQL adapter (the review_decision doctrine) |
| `backend/app/application/services/document_annotation_service.py` | **new** — create/list/update/delete + `extracted_text()` resolving the linked intake item via the existing extraction use case |
| `backend/app/api/routes/document_viewer.py` | **new** — viewer routes (below); registered in `main.py` |
| `backend/scripts/init_db.py` | import the annotation model (SQLite quickstart table creation); stamp 0008 |
| `backend/app/tests/unit/test_document_annotations.py` | **new** — 7 tests |
| `backend/app/tests/integration/test_document_annotations_api.py` | **new** — 5 tests |

## Frontend — native viewer

| File | Change |
|---|---|
| `frontend/package.json` / `package-lock.json` | **new dependency** `pdfjs-dist@4.10.38` |
| `frontend/public/pdf.worker.min.mjs` | **new** — pdf.js worker asset (served from /public) |
| `frontend/src/components/features/documents/PdfViewer.tsx` | **new** — in-app PDF render (no download), prev/next/jump, zoom in/out, fit width/page, highlight/note/bookmark overlay |
| `frontend/src/components/features/documents/ExtractedTextPanel.tsx` | **new** — extracted-text pane: select text → highlight (text sync via `findTextHighlight`), page notes, annotation list with delete |
| `frontend/src/components/features/documents/DocumentViewer.tsx` | **new** — side-by-side composition (toggleable); non-PDF keeps the M3 `DocumentPreview` |
| `frontend/src/lib/pdf/textSync.ts` | **new** — pure normalized text→pdf-rect matcher |
| `frontend/src/lib/api/annotations.ts` | **new** — annotations/extracted-text client |
| `frontend/src/app/(main)/documents/[id]/page.tsx` | Preview section now renders `DocumentViewer` |
| `frontend/src/types/index.ts` | annotation + extracted-text types |
| `frontend/src/lib/api/annotations.test.ts`, `frontend/src/lib/pdf/textSync.test.ts`, `frontend/src/components/features/documents/DocumentViewer.test.tsx` | **new** — 13 tests |

## API surface added

- `GET /api/v1/documents/{id}/extracted-text` — linked intake item's extracted text (404 when none)
- `GET|POST /api/v1/documents/{id}/annotations`
- `PUT|DELETE /api/v1/documents/annotations/{annotation_id}`

## Database

- **Migration:** `alembic upgrade head` (0008_document_annotations); SQLite quickstart: `python scripts/init_db.py` (stamps 0008).

## Verification

- Backend suite: **1240 passed, 2 skipped**.
- Frontend: **48 vitest passed**, `tsc --noEmit` clean, `next build` clean.
- Manual: upload PDF → annotation CRUD (highlight/bookmark/note, update, delete, 401 gate) → intake→approve→commit → `extracted-text` returns the pipeline text → highlight persisted → download 200.
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
