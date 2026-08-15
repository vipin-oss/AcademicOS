# AcademicOS — Grounded Attribution Fix (ZIP-2) — Apply Steps

**Patch ZIP:** `AcademicOS_Grounded_Attribution_Fix.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/m11-ai-workspace`)
**Applies on top of:** commit `e323102` **+** the previously applied `AcademicOS_Retrieval_Formulation_Fix.zip` (ZIP-1). This ZIP **replaces both files that ZIP-1 changed** with their corrected final versions — it is a complete superset, so apply order is simply: ZIP-1 (already done), then this ZIP.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD          # expected: e3231026d2cb615c1f8cf0b16297398e2f043ed2
python --version            # 3.10+ expected
```

Verify ZIP-1 is present (it must be, since this fix corrects a ZIP-1 regression):

```powershell
Select-String -Path "backend\app\application\services\assistant_retrieval.py" -Pattern "_marker_at" -Quiet
# True => ZIP-1 applied
```

## 2. Backup the files being overwritten

```powershell
$backup = "E:\AcademicOS\.patch-backups\grounded-attribution-fix"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item "E:\AcademicOS\backend\app\application\services\assistant_retrieval.py" $backup
Copy-Item "E:\AcademicOS\backend\app\tests\unit\test_retrieval_plan.py" $backup
Write-Host "Backed up to $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_Grounded_Attribution_Fix.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths inside the ZIP are repository-relative and replace the files in place:
- `backend\app\application\services\assistant_retrieval.py` (complete corrected file)
- `backend\app\tests\unit\test_retrieval_plan.py` (complete corrected test file)
- `APPLY_STEPS.md`, `CHANGE_REPORT.md` (docs; overwrite the ZIP-1 copies at the repo root)

No manual file copying or editing needed.

## 4. Run the focused tests (backend)

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/unit/test_retrieval_plan.py -v
```

Expected: **35 passed** (29 from ZIP-1 + 6 new regression tests, including the exact
`"According to the source text of "Cblu Jan, 2024.pdf"…"` query which must plan to `('cblu',)`).

## 5. Run the retrieval/AI regression suites

```powershell
python -m pytest app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_assistant_retrieval.py app/tests/unit/test_assistant_memory.py app/tests/unit/test_document_content_commit.py app/tests/unit/test_search_index.py app/tests/unit/test_hybrid_search.py app/tests/integration/test_direct_upload_content_search.py app/tests/integration/test_document_content_search.py
```

Expected: **121 passed**.

## 6. Full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,729 passed, 2 skipped**. (If your machine runs the 9 Qdrant tests against a live
Qdrant — `docker compose up -d qdrant` — those should pass; they fail only without a Qdrant
server and are unrelated to this patch.)

## 7. Smoke test in the running app

1. Backend + frontend running as usual.
2. In the AI workspace, ask:
   - `According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference? Do not use or expand the acronym CBLU. Do not infer from the filename. Give only the conference name explicitly supported by the document.`
   - **Before this fix:** retrieved/cited `Topic20_8p7_Galvin.pdf` (and the "Folder import" session) — the CBLU PDF was never in the sources, and the correct answer could only have come from conversation history.
   - **After this fix:** the plan is `cblu`; `Cblu Jan, 2024.pdf` appears as a cited source whose SOURCE TEXT contains the conference name — the answer and the citation refer to the same document.
3. Also try `According to Cblu Jan, 2024.pdf, on what dates was the conference held?` — same expected behavior.

## 8. Rollback

```powershell
Copy-Item "$backup\assistant_retrieval.py" "E:\AcademicOS\backend\app\application\services\assistant_retrieval.py" -Force
Copy-Item "$backup\test_retrieval_plan.py" "E:\AcademicOS\backend\app\tests\unit\test_retrieval_plan.py" -Force
```

Pure code change: no database, no migration, no `.env`, no frontend — rollback is instant.
