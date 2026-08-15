# ADR-024 — Polymorphic span / provenance model (L1)

**Status:** ratified at L1. Implements Freeze-Contract ADR-003 ("every claim
binds ≥1 span (document_id, block/chunk, page, chars)") in a format-agnostic
form.

## Decision

A **Span** is a source-local region. `page` is ONE supported kind, never the
universal abstraction. Supported span kinds:

`page`, `block`, `text_range`, `region`, `bbox`, `table`, `table_cell`,
`image_region`, `equation`, `diagram`, `slide`, `spreadsheet_cell`,
`spreadsheet_range`, `source_local`.

Spans are stored polymorphically (kind discriminator + scalar anchors + a
JSON `region` payload). `document_chunks` gain `page` and `region_json`
anchors so chunks are not page-bound.

## Rules

1. A claim binds ≥1 span; each span resolves to a stored Source and, for
   visual material, to the original blob (evidence).
2. Page/block/char spans are supported for paged documents; bbox/cell/slide/
   equation regions cover images, tables, spreadsheets, slides, and equations.
3. Equation blocks are **stored** now (a CDM block of type `equation` with an
   optional formula/region); structured equation *parsing* is L14.
4. L1 stores spans; the engines that produce them are L2.

## Consequences

No model redesign when the first non-page engines (images, XLSX, PPTX) land.
