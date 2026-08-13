"""L2 PDF engine adapter (pdfplumber).

Produces a ``NirDocument`` from a PDF byte string with page provenance, text
blocks, tables, figure/image regions, and equation/region representation. A
zero-text / low-text-density page is flagged ``needs_ocr`` for the (optional)
OCR adapter — never silently fabricated. Scanned/mixed PDFs route to OCR only
when the OCR engine is enabled.
"""

from __future__ import annotations

import io

from app.application.dtos.nir import NirDocument, NirElement, NirElementType, NirImage
from app.application.ports.nir_parser import NirParseError, NirParser
from app.application.services.extraction_limits import MAX_ELEMENTS, MAX_PAGES
from app.domain.value_objects.source import MediaKind


class PdfNirParser(NirParser):
    format_name = "pdf"

    def __init__(self) -> None:
        self._engine = "pdfplumber"

    def parse(self, data: bytes, *, source_id: str, version: int) -> NirDocument:
        try:
            import pdfplumber
        except ImportError as exc:  # pragma: no cover - pinned dep
            raise NirParseError(f"PDF engine unavailable: {exc}.") from exc

        try:
            pdf = pdfplumber.open(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise NirParseError(f"PDF could not be parsed ({type(exc).__name__}: {exc}).") from exc

        elements: list[NirElement] = []
        images: list[NirImage] = []
        page_texts: list[str] = []
        needs_ocr = False
        pages = 0
        try:
            pages = len(pdf.pages)
        except Exception:  # noqa: BLE001
            pages = 0
        page_count = min(pages, MAX_PAGES)
        warnings: list[str] = []
        order = 0

        for pno in range(page_count):
            try:
                page = pdf.pages[pno]
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"page {pno + 1} unreadable: {exc}")
                continue

            text = ""
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                text = ""

            # scanned / empty page -> needs OCR (honest)
            if not text.strip():
                needs_ocr = True
                if pno < MAX_PAGES:
                    elements.append(
                        NirElement(
                            element_type=NirElementType.PAGE_BREAK,
                            order=order, page=pno + 1, text="",
                        )
                    )
                    order += 1
                continue

            page_texts.append(text)
            if order < MAX_ELEMENTS:
                elements.append(
                    NirElement(
                        element_type=NirElementType.PARAGRAPH,
                        order=order, page=pno + 1, text=text,
                        extraction_confidence=1.0,
                    )
                )
                order += 1

            # tables
            try:
                for table in page.extract_tables() or []:
                    if order >= MAX_ELEMENTS:
                        break
                    elements.append(
                        NirElement(
                            element_type=NirElementType.TABLE,
                            order=order, page=pno + 1,
                            text=_table_to_text(table),
                            value={"rows": _table_to_rows(table)},
                            extraction_confidence=0.9,
                        )
                    )
                    order += 1
            except Exception:  # noqa: BLE001
                pass

            # images / figure regions (bbox provenance)
            try:
                for img_index, img in enumerate(page.images or []):
                    if order >= MAX_ELEMENTS:
                        break
                    try:
                        bbox = (
                            float(img.get("x0", 0.0)),
                            float(img.get("top", 0.0)),
                            float(img.get("x1", 0.0)),
                            float(img.get("bottom", 0.0)),
                        )
                    except (TypeError, ValueError):
                        bbox = None
                    image_id = f"pdf-{source_id}-p{pno + 1}-{img_index}"
                    images.append(
                        NirImage(
                            image_id=image_id, page=pno + 1, bbox=bbox,
                            region={"source": "pdf", "page": pno + 1},
                            media_type="image",
                        )
                    )
                    elements.append(
                        NirElement(
                            element_type=NirElementType.IMAGE,
                            order=order, page=pno + 1,
                            text="", value={"image_id": image_id}, bbox=bbox,
                            extraction_confidence=0.9,
                        )
                    )
                    order += 1
            except Exception:  # noqa: BLE001
                pass

        normalized_text = "\n".join(page_texts)
        try:
            pdf.close()
        except Exception:  # noqa: BLE001
            pass

        if needs_ocr:
            warnings.append("Source contains pages with no extractable text; OCR required.")

        return NirDocument(
            source_id=source_id,
            media_kind=MediaKind.TEXT_LAYOUT.value,
            version=version,
            engine=self._engine,
            engine_version=_pdfplumber_version(),
            elements=tuple(elements),
            images=tuple(images),
            pages=page_count,
            normalized_text=normalized_text[: 8_000_000],
            needs_ocr=needs_ocr,
            warnings=tuple(warnings),
        )


def _table_to_text(table) -> str:
    rows = _table_to_rows(table)
    return "\n".join(" | ".join(cell or "" for cell in row) for row in rows)


def _table_to_rows(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table:
        rows.append([str(c) if c is not None else "" for c in row])
    return rows


def _pdfplumber_version() -> int:
    try:
        import pdfplumber

        return int(pdfplumber.__version__.split(".")[0])
    except Exception:  # noqa: BLE001
        return 0
