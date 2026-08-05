"""Extraction adapters (infrastructure) — Intake M2 Part 1.

Concrete deterministic readers behind ``ports/document_parser.py``:

- ``PdfParser`` — pypdf adapter (text, page count, docinfo);
- ``DocxParser`` — python-docx adapter (paragraph text, core properties);
- text families — re-export of the stdlib application parser, composed here
  so the whole registry builds from one place.

``build_document_parsers()`` is the composition helper used by every
composition root (API routes, test harnesses).
"""
from app.application.intake.extraction.text_parsing import TextFamilyParser
from app.application.ports.document_parser import DocumentParser
from app.infrastructure.extraction.parsers import DocxParser, PdfParser


def build_document_parsers() -> dict[str, DocumentParser]:
    """The M2 parser registry: every family in ``SUPPORTED_FORMATS``."""

    return {
        "pdf": PdfParser(),
        "docx": DocxParser(),
        "text": TextFamilyParser("text"),
        "markdown": TextFamilyParser("markdown"),
        "csv": TextFamilyParser("csv"),
        "json": TextFamilyParser("json"),
    }


__all__ = ["DocxParser", "PdfParser", "TextFamilyParser", "build_document_parsers"]
