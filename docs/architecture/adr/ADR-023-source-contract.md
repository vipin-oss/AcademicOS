# ADR-023 — Format-agnostic SOURCE contract (L1)

**Status:** ratified at L1. Implements Freeze-Contract ADR-001 (source identity)
and the product vision that images, spreadsheets, slides, and packages are
first-class inputs. Does **not** create any parser/OCR/vision engine.

## Decision

Every ingested artifact is a **Source** described by a media kind and bound to
the **original blob** as evidence. The contract distinguishes (never conflates):

- `source identity`   -> the `document` UniversalObject id
- `file identity`     -> raw-bytes sha256 (`intake.sha256`) or normalized-text
  content hash (`document_registry`)
- `file version`      -> `object_versions` snapshot + object version number
- `media / container kind` -> `MediaKind` (text_layout, spreadsheet,
  raster_image, slides, plain_text, package, unknown), independent of parser
- `original blob`     -> a stable `FileStorage` key (evidence binding)
- `provenance`        -> engine + engine_version + provenance enum
- `processing state`  -> intake stage + `needs_ocr` honesty signal

A ZIP/package is a Source whose members are each independent Sources that
carry `container_source_id` + `container_path` (package provenance), so every
member is independently identifiable and unsupported/corrupt members never
silently disappear.

## Rules

1. A `document` object stores its source contract as system metadata
   (`source.media_kind`, `source.blob_key`, `source.container_id`,
   `source.container_path`, `source.engine`, `source.engine_version`,
   `source.extraction_state`).
2. Every derived artifact (span, claim, CDM block, chunk, ACL scope) traces
   back to a Source and, through it, to the original blob.
3. L1 registers the contract only. Parsing/OCR/vision (L2) plug adapters
   behind the existing `DocumentParser` / `FileStorage` ports and write
   through the L1 contracts.
4. Unknown media is `MediaKind.UNKNOWN`, surfaced honestly, never guessed.

## Consequences

PDF/OCR/DOCX/XLSX/PPTX/images/ZIP engines can be added at L2 without
redesigning identity, provenance, ACL, spans, claims, or CDM.
