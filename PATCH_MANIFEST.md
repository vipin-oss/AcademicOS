# AcademicOS M10 — Complete Incremental Patch Manifest

**Milestone:** M10 (Complete) — Document Workspace + Windows Automation
**Baseline (M9):** `c438ff3c946ddb29f43762fab425d39fe378adeb`
**Patch HEAD:** `e75e0eb1564dc980164dd884994a5e249425afe3`
**Date:** 2026-08-07

This is the **single official M10 patch**: it upgrades an M9 installation
directly to the complete M10 release (native PDF viewer + annotation
framework + document workspace + Windows automation). Apply once; do not
apply any other M10 patch.

---

## Feature Summary (all delivered by this patch)

1. Native PDF Viewer (pdf.js) — navigation, zoom, fit width/page
2. Annotation Framework — highlight / note / bookmark, persisted in PostgreSQL
3. PDF Full-Text Search — Ctrl+F, match highlight, prev/next, counter, case/whole-word
4. Thumbnail Sidebar — lazy, virtualized, click-to-jump, current-page indicator
5. Multi-Document Workspace — tabs, per-tab state, memory cleanup, restore
6. Image Viewer — PNG/JPG/JPEG/TIFF/SVG, zoom, pan, fit width/screen
7. Office Preview — DOCX/PPTX/XLSX read-only + download fallback
8. Citation Workspace — copy citation / page / paragraph references
9. AI Selection Hooks — Explain/Summarize/Rewrite extension points (no fake AI), Highlight/Note/Bookmark implemented
10. Knowledge-Graph Integration — metadata object links → `/objects/{id}`
11. Viewer Performance — lazy rendering, virtualization, memory cleanup
12. Accessibility — keyboard shortcuts, aria labels, focus management
13. Windows Automation Scripts — start/stop/health/apply-patch/reset/validate
14. README + CHANGELOG updates
15. Migration 0008 + `pdfjs-dist` dependency

---

## Files Added

| Path | Purpose |
|---|---|
| `backend/alembic/versions/0008_document_annotations.py` | Migration: `document_annotations` table |
| `backend/app/infrastructure/db/models/annotation_model.py` | Annotation table model |
| `backend/app/application/dtos/annotation.py` | `DocumentAnnotation` record + invariants |
| `backend/app/application/ports/annotation_store.py` | `AnnotationStore` port |
| `backend/app/infrastructure/persistence/annotation_store.py` | SQL adapter |
| `backend/app/application/services/document_annotation_service.py` | Annotation lifecycle + extracted-text resolution |
| `backend/app/api/routes/document_viewer.py` | Viewer routes |
| `backend/app/tests/unit/test_document_annotations.py` | 7 unit tests |
| `backend/app/tests/integration/test_document_annotations_api.py` | 5 integration tests |
| `frontend/public/pdf.worker.min.mjs` | pdf.js worker asset |
| `frontend/src/components/features/documents/PdfViewer.tsx` | Native PDF render + search overlay |
| `frontend/src/components/features/documents/PdfSearchPanel.tsx` | Ctrl+F search panel |
| `frontend/src/components/features/documents/ThumbnailSidebar.tsx` | Virtualized thumbnails |
| `frontend/src/components/features/documents/DocumentWorkspace.tsx` | Multi-tab workspace |
| `frontend/src/components/features/documents/DocumentViewer.tsx` | Type dispatcher |
| `frontend/src/components/features/documents/ExtractedTextPanel.tsx` | Side-by-side text + selection actions |
| `frontend/src/components/features/documents/ImageViewer.tsx` | Image viewer |
| `frontend/src/components/features/documents/OfficePreview.tsx` | Office preview + fallback |
| `frontend/src/components/features/documents/CitationPanel.tsx` + test | Citation workspace |
| `frontend/src/components/features/documents/SelectionActions.tsx` | AI hooks + highlight/note/bookmark |
| `frontend/src/components/features/documents/KgLinks.tsx` + test | KG object links |
| `frontend/src/app/(main)/documents/workspace/page.tsx` | Workspace route |
| `frontend/src/lib/pdf/textSync.ts` + test | Text→rect matcher |
| `frontend/src/lib/pdf/searchPdf.ts` + test | Full-text search matcher |
| `frontend/src/lib/api/annotations.ts` + test | Annotations client |
| `frontend/src/components/features/documents/DocumentViewer.test.tsx` | Dispatch tests |
| `scripts/windows/apply_patch.ps1` | Patch automation |
| `scripts/windows/start_academicos.ps1` | One-command startup |
| `scripts/windows/stop_academicos.ps1` | Graceful shutdown |
| `scripts/windows/reset_academicos.ps1` | Interactive reset menu |
| `scripts/windows/health_check.ps1` | Health check |
| `scripts/windows/validate_environment.ps1` | Env validation |
| `start.ps1` / `stop.ps1` / `health.ps1` / `apply_patch.ps1` | Root launchers |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/main.py` | Register viewer router |
| `backend/scripts/init_db.py` | Import annotation model; stamp 0008 |
| `frontend/package.json` / `package-lock.json` | +`pdfjs-dist@4.10.38` |
| `frontend/src/app/(main)/documents/[id]/page.tsx` | DocumentViewer + Citation + KgLinks panels |
| `frontend/src/components/features/documents/FileIcon.tsx` | Image type icons |
| `frontend/src/types/index.ts` | Annotation types + png/jpg/jpeg/tiff/svg |
| `README.md` | Windows automation + usage |
| `CHANGELOG.md` | M10 entries |

## Files Deleted

*(none)*

## Database Migrations

- **PostgreSQL:** `alembic upgrade head` → applies `0008_document_annotations`.
- **SQLite quickstart:** `python scripts/init_db.py` (recreates + stamps 0008).

## New Dependencies

- `pdfjs-dist==4.10.38` (frontend).

## Environment Variable Changes

*(none)*

## Commands Required After Applying

```powershell
# 1. Backend
cd backend
pip install -r requirements.txt        # (no change — alembic already pinned)
alembic upgrade head                   # PostgreSQL
# or
python scripts/init_db.py              # SQLite quickstart

# 2. Frontend
cd ..\frontend
npm install                            # pulls pdfjs-dist@4.10.38

# 3. Run (Windows automation)
cd ..
.\start.ps1                            # or manually: uvicorn + npm run dev
```

## Verification (performed on this patch)

- Backend suite: **1240 passed, 2 skipped** (includes 12 new viewer/annotation tests; M1–M9 suites unchanged and green).
- Frontend: **59 vitest passed**, `tsc --noEmit` clean, `next build` clean (0 export errors).
- Manual: PDF viewer (navigation/zoom/fit), annotations CRUD, extracted-text side-by-side, Ctrl+F search (highlight/nav/options), thumbnails, multi-tab workspace, image viewer, office preview, citation copy, selection actions, KG links, 401 gates, and the Windows automation scripts (start/stop/health/apply-patch/reset/validate).
