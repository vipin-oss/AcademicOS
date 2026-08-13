# AcademicOS — Knowledge Projection P0 — Apply Steps

**Patch ZIP:** `AcademicOS_Knowledge_Projection_P0.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/m11-ai-workspace`)
**Applies on top of:** `e323102` **+** ZIP-1 (Retrieval Formulation) **+** ZIP-2 (Grounded Attribution) **+** AI Foundation P0 **+** Evidence Architecture P0 (your current local state). This ZIP is the corrected P0 from the final red-team audit — it does NOT reintroduce any rejected design.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD          # expected: e3231026d2cb615c1f8cf0b16297398e2f043ed2
python --version            # 3.10+ expected
```

Verify the evidence-architecture baseline is present (this ZIP builds on it):

```powershell
Select-String -Path "backend\app\application\assistant\claim_support.py" -Pattern "ClaimSupportVerifier" -Quiet
# True => baseline present
```

## 2. Backup the files being overwritten

```powershell
$backup = "E:\AcademicOS\.patch-backups\knowledge-projection-p0"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\api\routes\documents.py",
  "backend\app\api\routes\search.py",
  "backend\app\application\ports\document_content_store.py",
  "backend\app\application\use_cases\intake\commit_item.py",
  "backend\app\infrastructure\db\models\document_content_model.py",
  "backend\app\infrastructure\persistence\document_content_store.py",
  "backend\app\infrastructure\search\document_content_rebuilder.py",
  "backend\app\infrastructure\search\index_applier.py",
  "backend\scripts\init_db.py",
  "backend\app\tests\unit\test_document_content_commit.py"
)
foreach ($f in $files) {
  Copy-Item (Join-Path "E:\AcademicOS" $f) (Join-Path $backup ($f -replace "\\", "."))
}
Write-Host "Backed up $($files.Count) files to $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_Knowledge_Projection_P0.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths are repository-relative; extraction replaces files in place and adds the new files listed in the manifest (migration 0010, chunk model/port/store, chunking service, 3 test files).

## 4. Apply the migration

For SQLite quickstart (your local dev):

```powershell
cd E:\AcademicOS\backend
$env:DATABASE_URL = "sqlite:///./academicos.db"
python scripts/init_db.py
# Expected: "Schema created and stamped at 0010_document_chunks."
```

For PostgreSQL: `alembic upgrade head` (migration `0010_document_chunks`). The migration is additive derived data — rollback = downgrade (drops the table + column).

## 5. Run the focused tests (backend)

```powershell
python -m pytest app/tests/unit/test_document_chunking.py app/tests/unit/test_document_chunk_lifecycle.py app/tests/integration/test_document_chunks_rebuild.py -v
```

Expected: **31 passed** (16 chunking incl. golden fixtures + 10 lifecycle + 5 rebuild/equivalence).

## 6. Run the retrieval/AI/evidence regression suites

```powershell
python -m pytest app/tests/unit/test_document_content_commit.py app/tests/unit/test_search_index.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_claim_support.py app/tests/unit/test_evidence_contract.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/integration/test_document_content_search.py app/tests/integration/test_direct_upload_content_search.py
```

Expected: **199 passed**.

## 7. Full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,816 passed, 2 skipped**. (The 9 Qdrant tests require a live Qdrant — `docker compose up -d qdrant` — they fail only without a server and are unrelated to this patch; identical on the pristine baseline.)

## 8. Frontend (unchanged, validate)

```powershell
cd E:\AcademicOS\frontend
npx vitest run          # expected: 101 passed
npm run typecheck       # expected: exit 0
```

## 9. Rebuild repair (one-time backfill of existing documents)

```powershell
cd E:\AcademicOS\backend
# creates content_hash + chunks for EVERY existing document (intake + direct upload)
curl -X POST http://127.0.0.1:8000/api/v1/search/content/rebuild -H "Authorization: Bearer <token>"
# or via the app: Settings → AI → "Rebuild document content"
```

This also repairs the direct-upload rebuild gap (existing direct uploads get content rows + chunks).

## 10. Smoke test

1. Upload any PDF via the Documents UI → open the AI workspace → ask a document-reference question.
2. `POST /search/content/rebuild` → repeat the question → same answer, same citation (rebuild equivalence).
3. Delete a document → ask about it → it must not appear in evidence.

## 11. Rollback

```powershell
foreach ($f in $files) {
  Copy-Item (Join-Path $backup ($f -replace "\\", ".")) (Join-Path "E:\AcademicOS" $f) -Force
}
Remove-Item "E:\AcademicOS\backend\app\application\services\document_chunking.py" -Force
Remove-Item "E:\AcademicOS\backend\app\application\ports\document_chunk_store.py" -Force
Remove-Item "E:\AcademicOS\backend\app\infrastructure\persistence\document_chunk_store.py" -Force
Remove-Item "E:\AcademicOS\backend\app\infrastructure\db\models\document_chunk_model.py" -Force
Remove-Item "E:\AcademicOS\backend\alembic\versions\0010_document_chunks.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\unit\test_document_chunking.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\unit\test_document_chunk_lifecycle.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\integration\test_document_chunks_rebuild.py" -Force
# DB: drop document_chunks + content_hash (or re-run init_db against a fresh DB)
```

The projection is derived data — rollback loses nothing authoritative.
