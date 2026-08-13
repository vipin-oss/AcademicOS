# AcademicOS — L2 Document Intelligence Engines

**Scope:** first actual document/media intelligence engine layer, format-agnostic
(ADR-028..031). L2 reuses all L1 contracts (Source/MediaKind, polymorphic spans,
claims, CDM, acl_scope, confidence split, version supersession) — no parallel
storage model. No PDF-only pipeline; engines are infrastructure adapters.

## What this milestone establishes
- **NIR (ADR-028):** transient, format-agnostic engine output contract
  (`app/application/dtos/nir.py`) that can represent text, regions, tables,
  spreadsheet cells/ranges, slides, images/regions, equations, diagrams,
  bboxes, source offsets, page/slide/sheet/member identity, extraction
  confidence, and source/version binding. NIR mapper writes into L1 CDM/span.
- **Engines (infrastructure):** pdfplumber (PDF text/tables/regions + scanned
  detection), python-docx (DOCX paragraphs/headings/tables), openpyxl (XLSX
  workbook/sheet/cell/range/formula), python-pptx (PPTX slides/text/tables/
  images/notes), Pillow (images, first-class), text family (TXT/MD/CSV/JSON),
  OCR adapter (ADR-030, optional + OFF by default).
- **Format detection (ADR-031):** extension + magic-bytes cross-check, honest
  MIME mismatch, never content-re-routing.
- **Container/package (ADR-029):** safe zipfile expander with member identity/
  provenance, path-traversal/bomb/depth/count/duplicate protection; corrupt or
  unsupported members explicitly reported, never silently dropped.
- **Security/resource limits:** `extraction_limits.py` + `container_policy.py`
  (max file/package/member/page/slide/sheet/cell/image/dimension/depth/ratio).
- **Ingestion integration:** `POST /documents/ingest` composes the existing
  document-creation flow with the L2 orchestrator (CDM + content projection);
  L1 version supersession cascade reused.
- **L1 closed:** LEVELS.md L1 `done`, L2 `in_progress`; ADR-028..031 ratified.

## Dependencies added (all MIT/HPND, pure-pip, pinned)
pdfplumber==0.11.10, openpyxl==3.1.5, python-pptx==1.0.2, Pillow==12.3.0.
OCR (pytesseract) is OPTIONAL/OFF by default and NOT added to requirements.

## Migrations
None. L1 storage (claims/claim_spans/cdm_blocks/acl_scope) is reused; container
provenance/media-kind live on document metadata. Alembic head stays 0012.

## L2 boundary (NOT implemented)
Classification, entity/relationship extraction, planner, retrieval rewrite,
frontend, L0/patch-farm changes — all out of scope.

## Verification
Backend pytest: 2008 passed, 2 skipped (includes 42 new L2 tests + guardrails).
Frontend vitest: 101 passed. tsc --noEmit: clean. git diff --check: clean.
L0/patch-farm/memory-fix/L1 boundaries unchanged.
