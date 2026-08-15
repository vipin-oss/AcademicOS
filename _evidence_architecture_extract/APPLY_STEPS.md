# AcademicOS — AI Evidence Architecture P1 Integration — Apply Steps

**Patch ZIP:** `AcademicOS_AI_Evidence_Architecture_P1_Integration.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/ai-knowledge-projection-p0`)
**Applies on top of:** P1 commit **`51547a2`** (`feat(ai): P1 retrieval layer — FTS projection, chunk evidence assembly, bounded retrieval`).
**What it does:** reconciles the missing Evidence Architecture P0 (claim→source verification) into the P1 architecture — the claim verifier operates on the **actual chunk/source evidence** the P1 prompt uses.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD        # must be 51547a2... (P1 commit)
git status --short        # should be clean (or only your own untracked files)
python --version          # 3.10+ expected
```

If HEAD is **not** 51547a2, stop and confirm the P1 commit is applied first.

## 2. Create a timestamped backup

```powershell
$backup = "E:\AcademicOS\.patch-backups\evidence-p1-integration-" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\application\assistant\claim_support.py",
  "backend\app\application\dtos\ai.py",
  "backend\app\application\use_cases\ai\grounded_qa.py",
  "backend\app\tests\unit\test_claim_support.py",
  "backend\app\tests\unit\test_evidence_contract.py",
  "backend\app\tests\integration\test_chunk_evidence_path.py"
)
foreach ($f in $files) {
  $src = Join-Path "E:\AcademicOS" $f
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $backup ($f -replace "\\", "."))
  }
}
Write-Host "Backup created at $backup"
```

## 3. Extract the ZIP

```powershell
Expand-Archive -Path "E:\AcademicOS\AcademicOS_AI_Evidence_Architecture_P1_Integration.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths inside the ZIP are repository-relative. Extraction places the six files at their correct locations **without overwriting anything else** (the ZIP contains exactly these six code/test files plus the two docs). Verify:

```powershell
Test-Path "E:\AcademicOS\backend\app\application\assistant\claim_support.py"   # True (new file)
Get-Item "E:\AcademicOS\backend\app\application\use_cases\ai\grounded_qa.py" | Select-Object LastWriteTime
```

## 4. Run the focused Evidence tests

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/unit/test_claim_support.py -q
python -m pytest app/tests/unit/test_evidence_contract.py -q
python -m pytest app/tests/integration/test_chunk_evidence_path.py -q
```

Expected: **26 + 16 + 7 = 49 passed**.

## 5. Run the P1 + retrieval regression tests

```powershell
python -m pytest app/tests/unit/test_fts_search.py app/tests/unit/test_chunk_evidence_assembly.py app/tests/unit/test_document_chunk_lifecycle.py app/tests/unit/test_document_chunking.py app/tests/integration/test_document_chunks_rebuild.py app/tests/unit/test_benchmark_harness.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/integration/test_document_content_search.py app/tests/integration/test_direct_upload_content_search.py -q
```

Expected: **green** (validated at 206 passed for the combined focused + regression set).

## 6. Run the full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,849 passed, 2 skipped**. Known non-regressions:
- 9 `test_qdrant_vector_repository.py` failures = **environment** (no Qdrant server; identical on the pristine baseline);
- `test_intake_api.py::test_pause_resume_completes_exactly_all_items` = **pre-existing flaky timing test** (passes standalone; fails only under full-suite load; untouched by this patch).

## 7. Migration required?

**NO.** This patch is pure Python — no database, no migration, no `.env`, no frontend, no schema change.

## 8. CBLU smoke test (optional but recommended)

Ask in the AI workspace:
`According to the source text of "Cblu Jan, 2024.pdf", what is the full name of the conference? Do not use or expand the acronym CBLU. Do not infer from the filename. Give only the conference name explicitly supported by the document.`

- **Supported answer** (exact conference name from the document body): returned with citation `[1] Cblu Jan, 2024.pdf`.
- **Unsupported answer** (e.g. "CBLU (Chaudhary Bansi Lal University)"): the UI shows the honest refusal — *"The answer could not be verified as a direct quote from 'Cblu Jan, 2024.pdf'…"* — with **no citation**.

## 9. Rollback

```powershell
foreach ($f in $files) {
  $src = Join-Path $backup ($f -replace "\\", ".")
  if (Test-Path $src) {
    Copy-Item $src (Join-Path "E:\AcademicOS" $f) -Force
  } else {
    Remove-Item (Join-Path "E:\AcademicOS" $f) -Force -ErrorAction SilentlyContinue
  }
}
Write-Host "Rolled back to P1 51547a2 state"
```

Pure code change — rollback is instant and complete.
