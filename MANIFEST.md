# AcademicOS — L1 Knowledge-Plane Contracts

**Scope:** the corrected L1 from the second-pass architecture audit. Format-
agnostic, image/package-aware contracts that L2 engines (PDF/OCR/vision) will
write into. No parser/OCR/vision/classification/planner engine is implemented.

## What this milestone establishes
- **Source contract (ADR-023):** format-agnostic Source + MediaKind (incl.
  raster_image / spreadsheet / slides / package) + original-blob evidence
  binding + container/package provenance.
- **Polymorphic spans (ADR-024):** page/block/text_range/bbox/table_cell/
  image_region/equation/diagram/slide/spreadsheet_cell; not page-only.
- **Confidence split (ADR-025):** extraction_confidence vs fact_confidence;
  OCR-derived fact confidence capped at medium.
- **acl_scope on every derived artifact (ADR-026):** search_documents,
  document_contents, document_chunks, document_search_fts, claims, cdm_blocks.
  Propagated by the single index consumer; stricter-of semantics.
- **Claim store (ADR-002/019):** claims + polymorphic claim_spans, bound to
  the predicate catalogue, raw fallback, PROPOSED/CONFIRMED/REJECTED/SUPERSEDED.
- **CDM block store (Blueprint §11):** format-agnostic blocks incl. equation,
  table, image_region, diagram, slide.
- **Version-replacement cascade (ADR-021/027):** new file version supersedes
  old claims/CDM and reproposes; supersede-not-delete.
- **OpenAPI surfaces (ADR-022):** /claims, /cdm, /confirmations routes.
- **L0 closed:** LEVELS.md marks L0 `done`, L1 `in_progress` (doc-only).
- **ADR-023..027** ratified.

## Migration
`backend/alembic/versions/0012_claims_cdm_spans_acl_scope.py` (chains off 0011).
Run `python -m alembic upgrade head` (PostgreSQL) or `python scripts/init_db.py`
(SQLite quickstart, stamps 0012). Additive; downgrade drops only L1 objects.

## L2 boundary (NOT implemented)
PDF parser / OCR / DOCX / XLSX / PPTX / image vision / ZIP extraction /
classification / entity / relationship / planner / retrieval — all future work
that writes into these L1 contracts.

## Verification
Backend pytest: 1966 passed, 2 skipped (includes 37 new L1 tests + architecture
guardrails). Frontend vitest: 101 passed. tsc --noEmit: clean. git diff --check:
clean. L0 artifacts, patch-farm allowlist, and the 9879d08 memory fix unchanged.
