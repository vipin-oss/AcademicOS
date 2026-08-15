"""L2 engine adapter tests (ADR-028): PDF/DOCX/XLSX/PPTX/image/OCR/container.

Uses compact in-memory generated fixtures (no large binary collections).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.application.ports.container_expander import ContainerExpandError
from app.application.ports.nir_parser import NirParseError
from app.infrastructure.extraction.nir_container import ZipContainerExpander
from app.infrastructure.extraction.nir_docx import DocxNirParser
from app.infrastructure.extraction.nir_image import ImageNirParser
from app.infrastructure.extraction.nir_ocr import TesseractOcrEngine
from app.infrastructure.extraction.nir_pdf import PdfNirParser
from app.infrastructure.extraction.nir_pptx import PptxNirParser
from app.infrastructure.extraction.nir_xlsx import XlsxNirParser
from app.tests.unit.extraction_fixtures import (
    make_docx_bytes,
    make_pdf_bytes,
    make_png_bytes,
    make_pptx_bytes,
    make_scanned_pdf_bytes,
    make_xlsx_bytes,
)


# --- PDF ---
def test_pdf_text_native():
    nir = PdfNirParser().parse(make_pdf_bytes("Hello L2"), source_id="s1", version=1)
    assert nir.media_kind == "text_layout"
    assert "Hello L2" in nir.text
    assert nir.pages == 1
    assert nir.needs_ocr is False


def test_pdf_corrupt_raises():
    with pytest.raises(NirParseError):
        PdfNirParser().parse(b"%PDF-1.4 fake", source_id="s1", version=1)


def test_pdf_scanned_flags_needs_ocr():
    nir = PdfNirParser().parse(make_scanned_pdf_bytes(), source_id="s1", version=1)
    assert nir.needs_ocr is True


# --- DOCX ---
def test_docx_paragraphs_and_headings():
    nir = DocxNirParser().parse(
        make_docx_bytes(["First para", "Second para"], title="T"), source_id="s2", version=1
    )
    assert nir.media_kind == "text_layout"
    assert any(e.text == "First para" for e in nir.elements)


def test_docx_corrupt_raises():
    with pytest.raises(NirParseError):
        DocxNirParser().parse(b"not a docx", source_id="s2", version=1)


# --- XLSX ---
def test_xlsx_sheets_cells():
    nir = XlsxNirParser().parse(
        make_xlsx_bytes([["Amount", 5000], ["Name", "Dr X"]]), source_id="s3", version=1
    )
    assert nir.media_kind == "spreadsheet"
    assert "Sheet1" in nir.sheets
    cells = [e for e in nir.elements if e.element_type.value == "sheet_cell"]
    assert any("Amount" in e.text for e in cells)


def test_xlsx_corrupt_raises():
    with pytest.raises(NirParseError):
        XlsxNirParser().parse(b"garbage", source_id="s3", version=1)


# --- PPTX ---
def test_pptx_slides():
    nir = PptxNirParser().parse(make_pptx_bytes(["Slide A", "Slide B"]), source_id="s4", version=1)
    assert nir.media_kind == "slides"
    assert nir.slides >= 1


# --- Image ---
def test_image_first_class():
    nir = ImageNirParser().parse(make_png_bytes(), source_id="s5", version=1)
    assert nir.media_kind == "raster_image"
    assert len(nir.images) == 1
    assert nir.needs_ocr is True  # OCR off -> honest signal


def test_image_bad_bytes_raises():
    with pytest.raises(NirParseError):
        ImageNirParser().parse(b"\x00\x01\x02", source_id="s5", version=1)


# --- OCR ---
def test_ocr_off_by_default():
    engine = TesseractOcrEngine()
    assert engine.available() is False


def test_ocr_confidence_is_separate():
    # OcrResult carries its own confidence field, distinct from fact confidence
    from app.application.ports.ocr_engine import OcrResult

    r = OcrResult(text="hello", confidence=0.8)
    assert r.confidence == 0.8
    assert r.text == "hello"


# --- Container ---
def test_zip_mixed_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", make_pdf_bytes("hello"))
        z.writestr("note.txt", b"plain")
    buf.seek(0)
    members = ZipContainerExpander().expand(buf.read())
    assert len(members) == 2
    assert all(m.ok for m in members)


def test_zip_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../evil.txt", b"x")
    buf.seek(0)
    with pytest.raises(ContainerExpandError):
        ZipContainerExpander().expand(buf.read())


def test_zip_corrupt_whole_raises():
    with pytest.raises(ContainerExpandError):
        ZipContainerExpander().expand(b"not a zip at all")


def test_zip_member_sha256():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.txt", b"abc")
    buf.seek(0)
    members = ZipContainerExpander().expand(buf.read())
    import hashlib

    assert members[0].sha256 == hashlib.sha256(b"abc").hexdigest()
