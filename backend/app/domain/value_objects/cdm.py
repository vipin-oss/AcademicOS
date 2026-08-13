"""Structured-document (CDM) block model (L1, Blueprint §11).

Format-agnostic block representation of a document's structure. The block
types cover paged documents (heading/section/table/figure/caption/footnote/
header/footer), visual structures (equation, image region, diagram), slide and
list structures — without being parser-specific. ``reading_order`` is carried
as data (``order`` + ``parent_block_id``), not as a claim.

L1 defines and stores CDM blocks; it does NOT implement structure detection
(that is an L2 engine that writes CDM blocks through the L1 contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CdmBlockType(str, Enum):
    HEADING = "heading"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    EQUATION = "equation"
    IMAGE_REGION = "image_region"
    DIAGRAM = "diagram"
    SLIDE = "slide"
    LIST = "list"
    METADATA = "metadata"
    OTHER = "other"


@dataclass(frozen=True)
class CdmBlock:
    block_id: str
    document_id: str
    version: int
    block_type: CdmBlockType
    order: int
    payload: dict[str, Any] = field(default_factory=dict)  # block content + span refs
    parent_block_id: str | None = None
    acl_scope: str | None = None
    page: int | None = None
    extraction_confidence: float | None = None  # ADR-004: separate from fact confidence

    def __post_init__(self) -> None:
        if self.extraction_confidence is not None and not (
            0.0 <= self.extraction_confidence <= 1.0
        ):
            raise ValueError("extraction_confidence must be between 0.0 and 1.0")


__all__ = ["CdmBlock", "CdmBlockType"]
