# ADR-051 — V3 M2: two PDF-reader ports are distinct; dead `/documents/ingest` removed

- **Status:** Accepted
- **Level:** V3 M2 (Correctness Repairs)
- **Supersedes:** nothing
- **Related:** ADR-028 (NIR contract), ADR-030 (OCR policy), ADR-022 (API freeze), V3 audit A2

## Context

Blueprint V3 M2 lists three correctness repairs: (1) the pypdf
`creation_date`/`modification_date` crash, (2) a written-but-unregistered
`ingest.py`, and (3) "unify the two PDF readers behind one port with one error
contract." Item (3) required reconciliation against the repository before
implementation, because the two "readers" are not interchangeable duplicates.

Evidence gathered at M2:

- `infrastructure/extraction/parsers.py::PdfParser` (pypdf) implements the
  `DocumentParser` port and returns `ExtractionResult` (text, page count,
  docinfo). It is the **live** upload/extract path: `routes/documents.py`,
  `routes/intake.py`, and `document_content_rebuilder.py` all call
  `build_document_parsers()`.
- `infrastructure/extraction/nir_pdf.py::PdfNirParser` (pdfplumber) implements
  the `NirParser` port and returns `NirDocument` (elements, tables, image
  regions, OCR flag). It is the **L2 document-intelligence engine** (ADR-028),
  consumed only by `ExtractionOrchestrator`.
- `ExtractionOrchestrator`'s only HTTP entry point was
  `routes/ingest.py::POST /documents/ingest`. `git log -S` shows that route was
  registered in the L2 commit (`0f80175`) and removed in L3 (`a8eaea9`) — it has
  been unreachable ever since, while the file remained. No test imports the
  router; every "ingest" reference in tests targets `ingest_blob` (the
  orchestrator) or ADR filenames about ingestion-scale.

## Decision

1. **The two PDF readers stay on two ports.** They encode different contracts
   (`ExtractionResult` vs `NirDocument`) at different layers (upload text
   extraction vs L2 structured intelligence). Merging them "behind one port"
   would collapse ADR-028's NIR contract — a destructive rewrite, not a repair.
2. **One error discipline is enforced instead.** The live `PdfParser` now shares
   the never-raise-on-best-effort-metadata discipline `PdfNirParser` already had:
   empty/malformed embedded dates yield `None`, engine failures still raise the
   port's error type (`ExtractionFailure` / `NirParseError`). This is the
   correct reading of "one error contract."
3. **`routes/ingest.py` is deleted.** It is a dead third upload entry point. Its
   L2 orchestration is still exercised directly by `test_l2_ingestion.py` /
   `test_l3_extraction_claim_bridge.py`, and the NIR engine is re-wired into the
   single canonical pipeline at M11 (One Document Pipeline) — it is not dead
   code and is not removed.

## Consequences

**Positive**
- The three named failing PDFs (empty/malformed `CreationDate`/`ModDate`) parse
  cleanly with `created_at`/`modified_at = None` instead of a 500.
- Exactly one live document pipeline remains for L2 re-wiring at M11; no third
  upload surface to reconcile.
- No architectural boundary is crossed: `DocumentParser` and `NirParser` both
  remain framework-free ports; the change is infrastructure-internal.

**Negative**
- Two PDF readers still exist (pypdf + pdfplumber). Accepted: they are two
  adapters on two ports, not two implementations of one port.

**Revisit when:** M11 (One Document Pipeline) chooses the canonical entry point;
at that time the `NirParser` registry becomes the single structured-reader
registry and the `DocumentParser` text-only path may be retired behind it.
