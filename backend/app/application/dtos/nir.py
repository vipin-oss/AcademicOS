"""Normalized Intermediate Representation (NIR) — L2 engine output contract.

A transient, format-agnostic DTO set (ADR-028). Engines (infrastructure) produce
a ``NirDocument``; the application NIR mapper converts it into the existing L1
``CdmBlock`` / ``Span`` / ``Claim``. The NIR is NOT a second persistent model.

It can represent (where available): text, page/document regions, tables,
spreadsheet cells/ranges, slides, images, image regions, equations, diagrams,
bounding boxes, character/source offsets, page/slide/sheet/member identity,
extraction confidence, and original source/version binding.

Stdlib + ``app.domain`` only (no engine libraries) so it stays in the
application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain.value_objects.span import Span, SpanKind


class NirElementType(str, Enum):
    """Every structural element the NIR can carry (mirrors CDM + span kinds)."""

    TEXT = "text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    EQUATION = "equation"
    IMAGE = "image"
    IMAGE_REGION = "image_region"
    DIAGRAM = "diagram"
    SLIDE = "slide"
    SHEET = "sheet"
    SHEET_CELL = "sheet_cell"
    METADATA = "metadata"
    PAGE_BREAK = "page_break"
    OTHER = "other"


@dataclass(frozen=True)
class NirImage:
    """One image element (embedded or standalone)."""

    image_id: str
    page: int | None = None
    slide: int | None = None
    sheet: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    region: dict[str, Any] = field(default_factory=dict)
    blob_key: str | None = None
    caption: str | None = None
    media_type: str | None = None
    width: int | None = None
    height: int | None = None
    extraction_confidence: float | None = None

    def span(self, source_id: str) -> Span:
        """A BBOX/IMAGE_REGION span resolving this image to its source."""
        kind = SpanKind.IMAGE_REGION
        return Span(
            kind=kind,
            source_id=source_id,
            page=self.page,
            slide=self.slide,
            bbox=self.bbox,
            payload=self.region,
        )


@dataclass(frozen=True)
class NirElement:
    """One structural element of a source."""

    element_type: NirElementType
    order: int
    text: str = ""
    value: dict[str, Any] = field(default_factory=dict)
    page: int | None = None
    slide: int | None = None
    sheet: str | None = None
    parent_id: str | None = None
    source_offset_start: int | None = None
    source_offset_end: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    extraction_confidence: float | None = None
    element_id: str | None = None

    def to_span(self, source_id: str) -> Span | None:
        """Derive a polymorphic Span from this element (best-effort)."""
        if self.bbox is not None:
            return Span(
                kind=SpanKind.BBOX, source_id=source_id, page=self.page,
                slide=self.slide, bbox=self.bbox,
            )
        if self.element_type is NirElementType.TABLE_CELL and self.value:
            return Span(
                kind=SpanKind.TABLE_CELL, source_id=source_id, page=self.page,
                table_id=str(self.value.get("table_id") or self.parent_id or ""),
                row_idx=self.value.get("row"),
                col_idx=self.value.get("col"),
                payload=self.value,
            )
        if self.element_type is NirElementType.EQUATION:
            return Span(
                kind=SpanKind.EQUATION, source_id=source_id, page=self.page,
                block_id=self.element_id, bbox=self.bbox,
            )
        if self.slide is not None:
            return Span(
                kind=SpanKind.SLIDE, source_id=source_id, slide=self.slide,
                bbox=self.bbox,
            )
        if self.page is not None:
            return Span(
                kind=SpanKind.PAGE, source_id=source_id, page=self.page,
                char_start=self.source_offset_start, char_end=self.source_offset_end,
            )
        if self.source_offset_start is not None and self.source_offset_end is not None:
            return Span(
                kind=SpanKind.TEXT_RANGE, source_id=source_id,
                char_start=self.source_offset_start, char_end=self.source_offset_end,
            )
        return None


@dataclass(frozen=True)
class NirDocument:
    """The transient output of one engine for one source blob."""

    source_id: str
    media_kind: str
    version: int
    engine: str
    engine_version: int
    elements: tuple[NirElement, ...] = field(default_factory=tuple)
    images: tuple[NirImage, ...] = field(default_factory=tuple)
    pages: int = 0
    sheets: tuple[str, ...] = ()
    slides: int = 0
    normalized_text: str = ""
    needs_ocr: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        """Flattened text for content projection (normalized_text preferred)."""
        return self.normalized_text or "\n".join(
            e.text for e in self.elements if e.text
        )


__all__ = [
    "NirDocument",
    "NirElement",
    "NirElementType",
    "NirImage",
]
