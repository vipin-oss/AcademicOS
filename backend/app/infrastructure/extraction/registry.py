"""L2 parser registry (composition root).

Builds the structured-parser registry + OCR engine + container expander so
composition roots (routes/test harnesses) wire everything from one place.
OCR is feature-flagged OFF by default (ADR-030).
"""

from __future__ import annotations

from typing import Any

from app.application.ports.container_expander import ContainerExpander
from app.application.ports.nir_parser import NirParser
from app.application.ports.ocr_engine import OcrEngine
from app.infrastructure.extraction.nir_container import ZipContainerExpander
from app.infrastructure.extraction.nir_docx import DocxNirParser
from app.infrastructure.extraction.nir_image import ImageNirParser
from app.infrastructure.extraction.nir_ocr import TesseractOcrEngine
from app.infrastructure.extraction.nir_pdf import PdfNirParser
from app.infrastructure.extraction.nir_pptx import PptxNirParser
from app.infrastructure.extraction.nir_text import TextNirParser
from app.infrastructure.extraction.nir_xlsx import XlsxNirParser


def build_ocr(settings: Any | None = None, *, enabled: bool = False) -> OcrEngine:
    """OCR adapter. Disabled by default (ADR-030)."""
    return TesseractOcrEngine(enabled=enabled)


def build_container_expander() -> ContainerExpander:
    return ZipContainerExpander()


def build_structured_parsers(
    *, ocr: OcrEngine | None = None, ocr_enabled: bool = False
) -> dict[str, NirParser]:
    """The L2 parser registry keyed by format family."""
    ocr = ocr or build_ocr(enabled=ocr_enabled)
    return {
        "pdf": PdfNirParser(),
        "docx": DocxNirParser(),
        "xlsx": XlsxNirParser(),
        "pptx": PptxNirParser(),
        "text": TextNirParser("text"),
        "markdown": TextNirParser("markdown"),
        "csv": TextNirParser("csv"),
        "json": TextNirParser("json"),
        "image": ImageNirParser(ocr=ocr),
        "png": ImageNirParser(ocr=ocr),
        "jpeg": ImageNirParser(ocr=ocr),
        "webp": ImageNirParser(ocr=ocr),
        "tiff": ImageNirParser(ocr=ocr),
        "bmp": ImageNirParser(ocr=ocr),
        "gif": ImageNirParser(ocr=ocr),
    }


__all__ = [
    "build_container_expander",
    "build_ocr",
    "build_structured_parsers",
]
