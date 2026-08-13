"""Polymorphic span / provenance model (L1, ADR-003).

A Span is a source-local region that a claim, a CDM block, or a citation binds
to. It is deliberately NOT page-centric: ``page`` is one span kind among many.
The model supports paged documents, spreadsheets, images, slides and equations
without making any one of them the universal abstraction.

Supported span kinds (each is an explicitly typed source-local region):

- PAGE            page number (paged documents)
- BLOCK           a logical block (heading/paragraph/figure/...) by id
- TEXT_RANGE      character range in normalized extracted text
- REGION          a named/coordinate region (e.g. a sub-area of a page)
- BBOX            an axis-aligned bounding box (images, figures, diagrams)
- TABLE           a whole table
- TABLE_CELL      a table cell (row/col)
- IMAGE_REGION    a region inside a raster/screenshot
- EQUATION         an equation/formula region (stored now; parsing is L14)
- DIAGRAM          a diagram region
- SLIDE           a slide index (PPTX)
- SPREADSHEET_CELL  a spreadsheet cell (row/col)
- SPREADSHEET_RANGE a spreadsheet cell range
- SOURCE_LOCAL     an engine-specific, typed local region (opaque JSON)

L1 stores spans; it does NOT implement the engines that produce them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpanKind(str, Enum):
    PAGE = "page"
    BLOCK = "block"
    TEXT_RANGE = "text_range"
    REGION = "region"
    BBOX = "bbox"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    IMAGE_REGION = "image_region"
    EQUATION = "equation"
    DIAGRAM = "diagram"
    SLIDE = "slide"
    SPREADSHEET_CELL = "spreadsheet_cell"
    SPREADSHEET_RANGE = "spreadsheet_range"
    SOURCE_LOCAL = "source_local"


@dataclass(frozen=True)
class Span:
    """One source-local region that provenance can point at.

    Only the fields relevant to ``kind`` are populated; the rest stay None.
    ``payload`` carries kind-specific data (e.g. bbox coordinates, a table
    cell ref, an opaque engine region) and is always JSON-serialisable.
    """

    kind: SpanKind
    source_id: str                       # document object id
    page: int | None = None              # PAGE / any paged source
    block_id: str | None = None          # BLOCK
    char_start: int | None = None        # TEXT_RANGE
    char_end: int | None = None          # TEXT_RANGE
    row_idx: int | None = None           # TABLE_CELL / SPREADSHEET_CELL
    col_idx: int | None = None           # TABLE_CELL / SPREADSHEET_CELL
    table_id: str | None = None          # TABLE / TABLE_CELL
    bbox: tuple[float, float, float, float] | None = None  # BBOX (x0,y0,x1,y1)
    slide: int | None = None             # SLIDE
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def region_label(self) -> str:
        """A short, deterministic human label for the region."""
        if self.kind is SpanKind.PAGE and self.page is not None:
            return f"page {self.page}"
        if self.kind is SpanKind.TEXT_RANGE:
            return f"chars {self.char_start}-{self.char_end}"
        if self.kind is SpanKind.TABLE_CELL:
            return f"table {self.table_id} cell {self.row_idx}:{self.col_idx}"
        if self.kind is SpanKind.SLIDE and self.slide is not None:
            return f"slide {self.slide}"
        return self.kind.value

    def to_region_dict(self) -> dict[str, Any]:
        """JSON-serialisable projection for persistence (claim_spans)."""
        data: dict[str, Any] = {
            "kind": self.kind.value,
            "source_id": self.source_id,
        }
        if self.page is not None:
            data["page"] = self.page
        if self.block_id is not None:
            data["block_id"] = self.block_id
        if self.char_start is not None:
            data["char_start"] = self.char_start
        if self.char_end is not None:
            data["char_end"] = self.char_end
        if self.row_idx is not None:
            data["row_idx"] = self.row_idx
        if self.col_idx is not None:
            data["col_idx"] = self.col_idx
        if self.table_id is not None:
            data["table_id"] = self.table_id
        if self.bbox is not None:
            data["bbox"] = list(self.bbox)
        if self.slide is not None:
            data["slide"] = self.slide
        if self.payload:
            data["payload"] = self.payload
        return data

    @classmethod
    def from_region_dict(cls, data: dict[str, Any]) -> Span:
        """Rebuild a Span from ``to_region_dict`` output."""
        bbox_raw = data.get("bbox")
        return cls(
            kind=SpanKind(data["kind"]),
            source_id=data["source_id"],
            page=data.get("page"),
            block_id=data.get("block_id"),
            char_start=data.get("char_start"),
            char_end=data.get("char_end"),
            row_idx=data.get("row_idx"),
            col_idx=data.get("col_idx"),
            table_id=data.get("table_id"),
            bbox=tuple(bbox_raw) if bbox_raw else None,
            slide=data.get("slide"),
            payload=data.get("payload") or {},
        )


__all__ = ["Span", "SpanKind"]
