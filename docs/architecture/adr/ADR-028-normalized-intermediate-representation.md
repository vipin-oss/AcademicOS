# ADR-028 — Normalized Intermediate Representation (NIR) (L2)

**Status:** ratified at L2. Establishes the format-agnostic engine output contract.

## Decision

Engines do NOT write directly to claims/CDM. Every format-specific engine
produces a **transient** Normalized Intermediate Representation (NIR) — a
stdlib-only application-layer DTO set that can represent:

- text and document/page regions
- tables and spreadsheet cells/ranges
- slides
- images and image regions
- equations and diagrams
- bounding boxes and character/source offsets
- page / slide / sheet / package-member identity
- extraction confidence
- original source/version binding

The NIR is an **engine output contract only** — it is NOT a second persistent
model. A format-agnostic NIR mapper converts `NirDocument` into the existing L1
`CdmBlock` / `Span` / `Claim` via `CdmService` / `ClaimService`. Storage stays
entirely within L1.

## Rules

1. NIR lives in `app.application.dtos.nir` and imports only stdlib + `app.domain`
   (it references the L1 `Span` value object).
2. Engines are infrastructure adapters that produce `NirDocument`; application
   never imports engine libraries.
3. `NirDocument.normalized_text` is the flattened searchable text; structured
   elements preserve the original structure (tables/cells/equations/images).
4. Adding a future format = a new engine adapter + a MediaKind entry; no NIR,
   CDM, claim, or schema change.

## Consequences

No format is hard-wired into the knowledge plane. A future format lands as a
new adapter against stable contracts, so it cannot force an L3/L4 rewrite.
