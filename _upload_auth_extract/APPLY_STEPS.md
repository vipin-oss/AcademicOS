# AcademicOS — Upload Auth Fix (P0) — Apply Steps

**Patch ZIP:** `AcademicOS_Upload_Auth_Fix.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/m11-ai-workspace`)
**Applies on top of:** commit `f746ac0` (`fix(ai): improve retrieval and direct upload content`) and any/all previously delivered ZIPs.

---

## 1. Prerequisite check

- PowerShell 5.1+ (or Windows PowerShell 7) — `powershell -Command $PSVersionTable.PSVersion`
- The repo is at `E:\AcademicOS` and the backend is currently running (the fix is frontend-only; you can apply it while the backend runs).
- Node.js + npm available (for the test step): `node --version && npm --version`

## 2. Backup files being overwritten

```powershell
$backup = "E:\AcademicOS\.patch-backups\upload-auth-fix"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item "E:\AcademicOS\frontend\src\lib\api\documents.ts" $backup
Write-Host "Backed up to $backup"
```

(If you re-apply later, the backup folder will hold the pre-patch version of `documents.ts`.)

## 3. Extract the ZIP

```powershell
$zip = "E:\AcademicOS\AcademicOS_Upload_Auth_Fix.zip"
Expand-Archive -Path $zip -DestinationPath "E:\AcademicOS" -Force
```

Paths inside the ZIP are repo-relative (`frontend\src\lib\api\documents.ts`, `frontend\src\lib\api\documents.test.ts`, plus `APPLY_STEPS.md` / `CHANGE_REPORT.md`), so extraction on top of `E:\AcademicOS` places each file at its correct location. No manual file copying is needed.

Verify the files landed:

```powershell
Test-Path "E:\AcademicOS\frontend\src\lib\api\documents.test.ts"   # should be True
Get-Item "E:\AcademicOS\frontend\src\lib\api\documents.ts" | Select-Object LastWriteTime, Length
```

## 4. Focused tests (frontend)

```powershell
cd E:\AcademicOS\frontend
npx vitest run src/lib/api/documents.test.ts src/lib/api/client.test.ts
```

Expected: **15 passed** (11 upload-auth + 4 shared-client auth).

Then the full frontend suite:

```powershell
npx vitest run
```

Expected: **101 passed** (20 files).

## 5. Frontend validation

```powershell
npm run typecheck
```

Expected: exits 0, no output. (Optional: `npm run build`.)

## 6. Smoke test in the running app (optional but recommended)

1. Backend running on `127.0.0.1:8000`; start the frontend: `npm run dev`.
2. Open `http://127.0.0.1:3000/login`, sign in.
3. Go to **Documents** → **Upload Document**, pick a PDF whose interesting fact is only in the body, submit.
4. Expected: the modal closes, the document appears in the list (previously this returned **401 "Your session has expired"**).
5. Ask Academic AI about a fact only present inside the PDF body — the answer should cite the document.

## 7. Rollback

```powershell
Copy-Item "E:\AcademicOS\.patch-backups\upload-auth-fix\documents.ts" "E:\AcademicOS\frontend\src\lib\api\documents.ts" -Force
Remove-Item "E:\AcademicOS\frontend\src\lib\api\documents.test.ts"
```

The fix is a pure frontend change: no database, no migration, no `.env`, no backend change — rollback is instant and complete.
