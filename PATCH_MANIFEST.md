# AcademicOS M10 Final Polish — Incremental Patch Manifest

**Milestone:** M10 Final Polish (production release candidate hardening)
**Baseline:** `f613b2b` (M10 complete)
**Patch HEAD:** (this patch's commit)
**Date:** 2026-08-07

This patch contains ONLY the engineering-review improvements over the
completed M10 release. Apply it over an M10 installation; it is additive
and backward compatible (no M1–M10 behavior is removed).

---

## Files Modified

| Path | Change |
|---|---|
| `scripts/windows/start_academicos.ps1` | Fixed same-file stdout/stderr redirect bug; fast TcpClient port probe; ASCII-safe output |
| `scripts/windows/apply_patch.ps1` | Removed dead backup variable; consistent conflict detection; ASCII-safe output |
| `scripts/windows/health_check.ps1` | Fast port probe; DB-file existence check |
| `scripts/windows/validate_environment.ps1` | Numeric Node major check; backend dir resolution from any cwd |
| `scripts/windows/stop_academicos.ps1` | ASCII-safe output |
| `scripts/windows/reset_academicos.ps1` | ASCII-safe output |
| `frontend/src/components/features/documents/PdfViewer.tsx` | Controlled page/scale/fitMode props (per-tab state actually preserved); pdf.js destroy on unmount |
| `frontend/src/components/features/documents/DocumentWorkspace.tsx` | All tabs stay mounted (state survives switching); fitMode in tab state; close → unmount → PdfViewer frees the document |
| `frontend/src/components/features/documents/DocumentViewer.tsx` | `onPageChange` lifting for the citation panel |
| `frontend/src/app/(main)/documents/[id]/page.tsx` | Live viewer page drives CitationPanel page reference |
| `frontend/src/components/features/documents/OfficePreview.tsx` | Real JSZip parsing + authenticated download fallback |
| `frontend/src/lib/documents/officeText.ts` | DOCX/PPTX/XLSX text extraction (FileReader arrayBuffer for jsdom) |
| `frontend/src/lib/documents/download.ts` | Shared authenticated download helper |
| `frontend/src/components/features/documents/ImageViewer.tsx` | Image error → inline fallback with download |
| `frontend/src/components/features/documents/KgLinks.tsx` | Fetches attached object metadata; own-object link |
| `frontend/src/components/features/documents/ExtractedTextPanel.tsx` | Removed duplicate highlight button; selection preview |
| `frontend/src/components/features/documents/KgLinks.test.ts` | Updated to the metadata-record signature |
| `frontend/package.json` / `package-lock.json` | +`jszip@3.10.1` |
| `CHANGELOG.md` | M10 Final Polish entry |

## Files Added

| Path | Purpose |
|---|---|
| `frontend/src/lib/documents/officeText.test.ts` | 5 office-extraction tests |
| `frontend/src/lib/documents/officeText.ts` | Office package text extraction (JSZip) |
| `frontend/src/lib/documents/download.ts` | Authenticated download helper |

## Files Deleted

*(none)*

## Database Migrations

*(none)*

## New Dependencies

- `jszip@3.10.1` (frontend) — `cd frontend && npm install` after applying.

## Environment Variable Changes

*(none)*

## Commands Required After Applying

```powershell
cd frontend && npm install
```

## Verification

- Backend suite: **1240 passed, 2 skipped**.
- Frontend: **64 vitest passed**, `tsc --noEmit` clean, `next build` clean (0 export errors).
