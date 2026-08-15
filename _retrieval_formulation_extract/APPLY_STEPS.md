# AcademicOS — Retrieval Formulation Fix (ZIP-1) — Apply Steps

**Patch ZIP:** `AcademicOS_Retrieval_Formulation_Fix.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/m11-ai-workspace`)
**Baseline:** commit `e323102` (`fix(upload): attach auth token to document uploads`) — this ZIP is built directly from that commit and applies on top of it.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD          # must print e3231026d2cb615c1f8cf0b16297398e2f043ed2
git status --short          # should be empty (or only your local untracked files)
python --version            # 3.10+ expected
```

If HEAD is NOT `e323102`, still safe to apply (the two files are self-contained), but note the mismatch.

## 2. Backup the files being overwritten

```powershell
$backup = "E:\AcademicOS\.patch-backups\retrieval-formulation-fix"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item "E:\AcademicOS\backend\app\application\services\assistant_retrieval.py" $backup
Copy-Item "E:\AcademicOS\backend\app\tests\unit\test_retrieval_plan.py" $backup
Write-Host "Backed up to $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_Retrieval_Formulation_Fix.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths inside the ZIP are repository-relative (`backend\app\application\services\assistant_retrieval.py`, `backend\app\tests\unit\test_retrieval_plan.py`, plus `APPLY_STEPS.md` / `CHANGE_REPORT.md`), so extraction on top of `E:\AcademicOS` replaces the files in place. No manual copying or editing needed.

Verify:

```powershell
Get-Item "E:\AcademicOS\backend\app\application\services\assistant_retrieval.py" | Select-Object LastWriteTime, Length
```

## 4. Run the focused tests (backend)

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/unit/test_retrieval_plan.py -v
```

Expected: **29 passed** (18 existing + 11 new regression tests, including the historical `"mation"` failure).

## 5. Run the retrieval/AI regression suites

```powershell
python -m pytest app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_assistant_retrieval.py app/tests/unit/test_assistant_memory.py app/tests/unit/test_document_content_commit.py app/tests/unit/test_search_index.py app/tests/unit/test_hybrid_search.py app/tests/integration/test_direct_upload_content_search.py app/tests/integration/test_document_content_search.py
```

Expected: **121 passed** (verified on the same code in the audit environment).

## 6. Full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,723 passed, 2 skipped**. (If your machine runs the 9 Qdrant tests against a live Qdrant — `docker compose up -d qdrant` — those 9 should also pass; they failed only in the audit sandbox because no Qdrant server was running. They are unrelated to this patch.)

## 7. Smoke test in the running app

1. Backend + frontend running (as usual).
2. Ask in the AI workspace:
   - `What is the exact name of the conference mentioned in the Cblu Jan, 2024.pdf? Do not infer from the filename. Quote only the information supported by the document.`
   - Expected: the CBLU PDF appears as source `[1]` and the answer quotes the conference name from the PDF body (previously the wrong sources appeared / the answer guessed "CERTIFICATE").
   - `Which conference did I attend in January 2024?` — expected: event-scoped retrieval.

## 8. Rollback

```powershell
Copy-Item "$backup\assistant_retrieval.py" "E:\AcademicOS\backend\app\application\services\assistant_retrieval.py" -Force
Copy-Item "$backup\test_retrieval_plan.py" "E:\AcademicOS\backend\app\tests\unit\test_retrieval_plan.py" -Force
```

Pure code change: no database, no migration, no `.env`, no frontend — rollback is instant.
