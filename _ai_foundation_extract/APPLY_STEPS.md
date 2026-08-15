# AcademicOS — AI Foundation P0 — Apply Steps

**Patch ZIP:** `AcademicOS_AI_Foundation_P0.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/m11-ai-workspace`)
**Applies on top of:** `e323102` **+** ZIP-1 (`AcademicOS_Retrieval_Formulation_Fix`) **+** ZIP-2 (`AcademicOS_Grounded_Attribution_Fix`) — i.e., your current local state. This ZIP **replaces the files those ZIPs changed** with the corrected superset versions, so apply it LAST.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD          # expected: e3231026d2cb615c1f8cf0b16297398e2f043ed2
python --version            # 3.10+ expected
```

Verify your current state has ZIP-1 and ZIP-2 applied (the foundation builds on them):

```powershell
Select-String -Path "backend\app\application\services\assistant_retrieval.py" -Pattern "_marker_at" -Quiet
Select-String -Path "backend\app\application\services\assistant_retrieval.py" -Pattern "_starts_document_name" -Quiet
# both True => ZIP-1 + ZIP-2 present
```

## 2. Backup the files being overwritten

```powershell
$backup = "E:\AcademicOS\.patch-backups\ai-foundation-p0"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\application\dtos\assistant.py",
  "backend\app\application\services\assistant_retrieval.py",
  "backend\app\application\use_cases\ai\grounded_qa.py",
  "backend\app\application\use_cases\search\search_objects.py",
  "backend\app\infrastructure\repositories\sqlalchemy_search_repository.py",
  "backend\app\tests\unit\test_retrieval_excludes_internal_types.py",
  "backend\app\tests\unit\test_retrieval_plan.py"
)
foreach ($f in $files) {
  $dest = Join-Path $backup ($f -replace "\\", ".")
  Copy-Item (Join-Path "E:\AcademicOS" $f) $dest
}
Write-Host "Backed up $($files.Count) files to $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_AI_Foundation_P0.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths are repository-relative; extraction replaces files in place. New file:
`backend\app\tests\unit\test_document_reference_resolution.py`.

## 4. Run the focused tests (backend)

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_retrieval_excludes_internal_types.py -v
```

Expected: **56 passed** (14 new foundation tests + 35 plan tests + 7 exclusion tests).

## 5. Run the retrieval/AI regression suites

```powershell
python -m pytest app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_assistant_retrieval.py app/tests/unit/test_assistant_memory.py app/tests/unit/test_document_content_commit.py app/tests/unit/test_search_index.py app/tests/unit/test_hybrid_search.py app/tests/integration/test_direct_upload_content_search.py app/tests/integration/test_document_content_search.py
```

Expected: **114 passed** (+ 56 focused = 170 retrieval/AI tests green).

## 6. Full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,743 passed, 2 skipped**. (If your machine runs the 9 Qdrant tests against a live Qdrant — `docker compose up -d qdrant` — those pass too; they failed only in the audit sandbox without a Qdrant server and are unrelated to this patch.)

## 7. Smoke test in the running app (the historical failure)

1. Backend + frontend running as usual.
2. Ask exactly:
   `According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference? Do not use or expand the acronym CBLU. Do not infer from the filename. Give only the conference name explicitly supported by the document.`
   - **Expected now:** the plan resolves the document reference; sources show `[1] Cblu Jan, 2024.pdf`; the answer quotes the conference name from that PDF's source text.
   - **If the document is not in your corpus:** the assistant must now refuse honestly ("I could not verify the answer from the specified document …") instead of answering from other documents or conversation history.
3. Ask `When did I attend the CBLU conference?` — ordinary entity retrieval still works.
4. Ask `Which conference did I attend in January 2024?` — event-scoped retrieval still works.

## 8. Rollback

```powershell
foreach ($f in $files) {
  $src = Join-Path $backup ($f -replace "\\", ".")
  Copy-Item $src (Join-Path "E:\AcademicOS" $f) -Force
}
Remove-Item "E:\AcademicOS\backend\app\tests\unit\test_document_reference_resolution.py" -Force
```

Pure code change: no database, no migration, no `.env`, no frontend — rollback is instant.
