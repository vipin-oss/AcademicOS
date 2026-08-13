# AcademicOS — P1 Knowledge-Layer Scale & Identity — Apply Steps

**Patch ZIP:** `AcademicOS_KnowledgeLayer_Scale_Identity_P1.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/ai-knowledge-projection-p0`)
**Applies on top of:** **`e14aa6b`** (`Fix graph neighbor citation leakage`) — your current baseline.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD        # must be e14aa6b...
git status --short        # should be clean (or only your own untracked files)
python --version          # 3.10+ expected
```

## 2. Create a timestamped backup

```powershell
$backup = "E:\AcademicOS\.patch-backups\p1-scale-identity-" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\api\routes\search.py",
  "backend\app\infrastructure\db\models\document_content_model.py",
  "backend\app\infrastructure\repositories\sqlalchemy_search_repository.py",
  "backend\app\infrastructure\search\document_content_rebuilder.py",
  "backend\app\infrastructure\search\index_applier.py",
  "backend\scripts\init_db.py"
)
foreach ($f in $files) {
  Copy-Item (Join-Path "E:\AcademicOS" $f) (Join-Path $backup ($f -replace "\\", "."))
}
Write-Host "Backed up $($files.Count) files to $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_KnowledgeLayer_Scale_Identity_P1.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths are repository-relative. The ZIP contains exactly 6 modified production files, 5 new production files, 3 new test files, 1 benchmark script, and the 3 docs — nothing else is overwritten.

## 4. Apply the migration (schema for the new projections)

For SQLite quickstart (your local dev):

```powershell
cd E:\AcademicOS\backend
$env:DATABASE_URL = "sqlite:///./academicos.db"
python scripts/init_db.py
# Expected: "Schema created and stamped at 0011_search_fts_identity."
```

For PostgreSQL: `alembic upgrade head` (migration `0011_search_fts_identity`: `document_search_fts` tsvector+GIN, `document_registry`, content_hash index). The migration is additive derived data — rollback = downgrade.

## 5. Run the new P1 tests

```powershell
python -m pytest app/tests/unit/test_fts_search.py app/tests/unit/test_document_identity.py app/tests/integration/test_scale_identity_rebuild.py -v
```

Expected: **25 passed** (12 FTS + 8 identity + 5 scale/rebuild integration).

## 6. Run the regression suites

```powershell
python -m pytest app/tests/unit/test_claim_support.py app/tests/unit/test_evidence_contract.py app/tests/integration/test_chunk_evidence_path.py app/tests/integration/test_graph_citation_filter.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_assistant_retrieval.py app/tests/unit/test_assistant_memory.py app/tests/unit/test_document_content_commit.py app/tests/unit/test_document_chunking.py app/tests/unit/test_document_chunk_lifecycle.py app/tests/integration/test_document_chunks_rebuild.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_fast_ai_streaming.py -q
```

Expected: **green** (validated at 214 passed).

## 7. Run the full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,855 passed, 2 skipped**. Known pre-existing failures (unchanged, environment): 9 `test_qdrant_vector_repository.py` (no Qdrant server); 1 flaky intake timing test that passes standalone.

## 8. Run the benchmark (optional but recommended)

```powershell
python scripts/benchmark_p1.py --docs 100 1000 10000
```

Measured acceptance (validated): realistic-term retrieval at ~10k docs **< 20 ms** with a **bounded candidate set** (8); pathological 100%-match term reported separately.

## 9. Frontend (unchanged, validate)

```powershell
cd E:\AcademicOS\frontend
npx vitest run          # expected: 101 passed
npm run typecheck       # expected: exit 0
```

## 10. Smoke test

1. Upload the same PDF twice → both uploads succeed; the second is a detected duplicate (rebuild endpoint reports `duplicates` count; registry canonical = the deterministically chosen representative).
2. Ask a body-content question → the document is found via FTS; sources bounded to evidence actually used.
3. `POST /search/content/rebuild` → `{indexed, skipped, chunked, duplicates}`; identical behavior after re-asking the same question.

## 11. Rollback

```powershell
foreach ($f in $files) {
  Copy-Item (Join-Path $backup ($f -replace "\\", ".")) (Join-Path "E:\AcademicOS" $f) -Force
}
Remove-Item "E:\AcademicOS\backend\app\infrastructure\search\fts.py" -Force
Remove-Item "E:\AcademicOS\backend\app\application\ports\document_identity_store.py" -Force
Remove-Item "E:\AcademicOS\backend\app\infrastructure\db\models\document_identity_model.py" -Force
Remove-Item "E:\AcademicOS\backend\app\infrastructure\persistence\document_identity_store.py" -Force
Remove-Item "E:\AcademicOS\backend\alembic\versions\0011_search_fts_identity.py" -Force
Remove-Item "E:\AcademicOS\backend\scripts\benchmark_p1.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\unit\test_fts_search.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\unit\test_document_identity.py" -Force
Remove-Item "E:\AcademicOS\backend\app\tests\integration\test_scale_identity_rebuild.py" -Force
# DB: alembic downgrade -1 (drops document_search_fts, document_registry, content_hash index)
```

The projections are derived data — rollback loses nothing authoritative.
