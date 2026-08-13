# AcademicOS — Graph-Only Citation Filter (P1 maintenance) — Apply Steps

**Patch ZIP:** `AcademicOS_GraphCitation_Filter.zip`
**Target repo:** `E:\AcademicOS` (branch `feature/ai-knowledge-projection-p0`)
**Applies on top of:** **`0b83e71`** (`Integrate evidence architecture with P1 chunk retrieval`) — your current baseline.

---

## 1. Prerequisite check

```powershell
cd E:\AcademicOS
git rev-parse HEAD        # must be 0b83e71... (your current baseline)
git status --short        # should be clean (or only your own untracked files)
python --version          # 3.10+ expected
```

## 2. Create a timestamped backup

```powershell
$backup = "E:\AcademicOS\.patch-backups\graph-citation-filter-" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = @(
  "backend\app\application\assistant\prompt_builder.py",
  "backend\app\application\use_cases\ai\grounded_qa.py",
  "backend\app\tests\integration\test_graph_citation_filter.py"
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
Expand-Archive -Path "E:\AcademicOS\AcademicOS_GraphCitation_Filter.zip" -DestinationPath "E:\AcademicOS" -Force
```

All paths are repository-relative. The ZIP contains exactly two modified production files, one new test file, and the two docs — nothing else is overwritten. Verify:

```powershell
Test-Path "E:\AcademicOS\backend\app\tests\integration\test_graph_citation_filter.py"   # True (new)
```

## 4. Run the new focused regression tests

```powershell
cd E:\AcademicOS\backend
python -m pytest app/tests/integration/test_graph_citation_filter.py -v
```

Expected: **7 passed** (graph-only event not citable; metadata suppressed; graph-only document not numbered; search-hit event still citable; CBLU supported/unsupported unchanged).

## 5. Run the evidence + chunk + retrieval regression

```powershell
python -m pytest app/tests/unit/test_claim_support.py app/tests/unit/test_evidence_contract.py app/tests/integration/test_chunk_evidence_path.py app/tests/unit/test_grounded_qa.py app/tests/unit/test_chat.py app/tests/unit/test_assistant_retrieval.py app/tests/unit/test_assistant_memory.py app/tests/unit/test_document_content_commit.py app/tests/unit/test_document_chunking.py app/tests/unit/test_document_chunk_lifecycle.py app/tests/integration/test_document_chunks_rebuild.py app/tests/unit/test_retrieval_plan.py app/tests/unit/test_retrieval_excludes_internal_types.py app/tests/unit/test_document_reference_resolution.py app/tests/unit/test_fast_ai_streaming.py -q
```

Expected: **green** (validated at 214 passed on a fresh clone).

## 6. Run the full backend suite (recommended)

```powershell
python -m pytest
```

Expected: green apart from the known pre-existing environment failures (9 Qdrant tests without a Qdrant server; 1 flaky intake timing test that passes standalone).

## 7. Migration required?

**NO.** Pure Python — no database, no migration, no `.env`, no frontend change.

## 8. Smoke test

1. Ask about the certificate (e.g. the paper title or organizer). The certificate must be the **only** displayed source — a related event reachable only via the graph link must NOT appear as a source, and its structured metadata must not leak into the answer.
2. Ask a question the event genuinely matches (e.g. "When was the Ku conference held?") — the event **is** displayed as a source with its metadata.

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
Write-Host "Rolled back to 0b83e71 state"
```

Pure code change — rollback is instant and complete.
