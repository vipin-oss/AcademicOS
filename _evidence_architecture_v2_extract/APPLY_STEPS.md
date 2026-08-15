# AcademicOS — AI Evidence Architecture P1 Integration v2 — Apply Steps

**Patch ZIP:** `AcademicOS_AI_Evidence_Architecture_P1_Integration_v2.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/ai-knowledge-projection-p0`)
**Applies on top of:** **`bd253b9`** (`Implement AI knowledge projection foundation`) — your actual current local baseline.
**Why v2:** the previous ZIP (v1) was built against the P1 commit `51547a2` (which exists only in the scratch environment) and imported `evidence_assembly.py` — a P1 file that is **not present in bd253b9** — so local test collection failed with `ModuleNotFoundError`. **v2 is self-consistent with bd253b9**: it includes every file required for the Evidence Architecture to import and execute, including the validated P1 `evidence_assembly.py` and the live-app chunk wiring in `routes/ai.py`.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD        # must be bd253b9... (your current baseline)
git status --short        # should be clean (or only your own untracked files)
python --version          # 3.10+ expected
```

## 2. Create a timestamped backup

```powershell
$backup = "E:\AcademicOS\.patch-backups\evidence-p1-integration-v2-" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\application\assistant\claim_support.py",
  "backend\app\application\services\evidence_assembly.py",
  "backend\app\application\dtos\ai.py",
  "backend\app\application\use_cases\ai\grounded_qa.py",
  "backend\app\api\routes\ai.py",
  "backend\app\tests\unit\test_claim_support.py",
  "backend\app\tests\unit\test_evidence_contract.py",
  "backend\app\tests\unit\test_chunk_evidence_assembly.py",
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
Expand-Archive -Path "E:\AcademicOS\AcademicOS_AI_Evidence_Architecture_P1_Integration_v2.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths are repository-relative. The ZIP contains exactly the nine code/test files (four new: `claim_support.py`, `evidence_assembly.py`, `test_claim_support.py`, `test_evidence_contract.py`; five replaced: `dtos/ai.py`, `grounded_qa.py`, `routes/ai.py`, `test_chunk_evidence_assembly.py`, `test_chunk_evidence_path.py`) plus the two docs. Nothing else is overwritten. Verify:

```powershell
Test-Path "E:\AcademicOS\backend\app\application\services\evidence_assembly.py"   # True (new)
Test-Path "E:\AcademicOS\backend\app\application\assistant\claim_support.py"      # True (new)
```

## 4. Run the focused Evidence tests (the exact command that previously failed)

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/unit/test_claim_support.py app/tests/unit/test_evidence_contract.py app/tests/integration/test_chunk_evidence_path.py -q
```

Expected: **26 + 16 + 7 = 49 passed** (no collection error).

## 5. Run the chunk-evidence unit test + P0/P1 chunk regression (present on bd253b9)

```powershell
python -m pytest app/tests/unit/test_chunk_evidence_assembly.py app/tests/unit/test_document_chunk_lifecycle.py app/tests/unit/test_document_chunking.py app/tests/integration/test_document_chunks_rebuild.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_fast_ai_streaming.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/integration/test_document_content_search.py app/tests/integration/test_direct_upload_content_search.py -q
```

Expected: **green** (validated at 49 focused + regression green on a fresh bd253b9 clone).

## 6. Run the full backend suite (recommended)

```powershell
python -m pytest
```

Expected: **1,849 passed, 2 skipped**-class result. Known non-regressions:
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
Write-Host "Rolled back to bd253b9 state"
```

Pure code change — rollback is instant and complete.
