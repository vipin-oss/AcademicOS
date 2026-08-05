"""Unit tests for the deterministic extraction parsers (Intake M2 Part 1).

The port lives in the application layer; the stdlib text-family parser beside
it; the pypdf/python-docx readers are infrastructure adapters — these tests
exercise all three through the same contract. Every assertion mirrors the
honesty rule: a field the file does not carry comes back ``None``/absent —
never inferred, never fabricated.
"""
from __future__ import annotations

import pytest

from app.application.dtos.extraction import PREVIEW_LIMIT, format_of
from app.application.intake.extraction.text_parsing import (
    TextFamilyParser,
    decode_text,
    extract_text_family,
    markdown_title,
)
from app.application.ports.document_parser import DocumentParser, ExtractionFailure
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.extraction.parsers import DocxParser, PdfParser
from app.tests.unit.extraction_fixtures import make_docx_bytes, make_pdf_bytes


class TestFormatTable:
    @pytest.mark.parametrize(
        ("extension", "expected"),
        [
            ("pdf", "pdf"),
            ("docx", "docx"),
            ("txt", "text"),
            ("md", "markdown"),
            ("markdown", "markdown"),
            ("csv", "csv"),
            ("json", "json"),
        ],
    )
    def test_supported_extensions_map_to_families(self, extension: str, expected: str) -> None:
        assert format_of(extension) == expected

    @pytest.mark.parametrize("extension", ["png", "xlsx", "pptx", "zip", "odt", "epub", "bin", ""])
    def test_other_formats_are_not_supported(self, extension: str) -> None:
        assert format_of(extension) is None


class TestRegistry:
    def test_registry_covers_every_supported_family(self) -> None:
        parsers = build_document_parsers()
        assert set(parsers) == {"pdf", "docx", "text", "markdown", "csv", "json"}
        for name, parser in parsers.items():
            assert isinstance(parser, DocumentParser)
            assert parser.format_name == name

    def test_registry_dispatch(self) -> None:
        parsers = build_document_parsers()
        assert parsers["text"].parse(b"plain").text == "plain"
        assert parsers["markdown"].parse(b"# T\nbody").document_title == "T"

    def test_non_text_family_rejected(self) -> None:
        with pytest.raises(ValueError, match="Not a text-family"):
            TextFamilyParser("pdf")


class TestDecodeText:
    def test_utf8_round_trip(self) -> None:
        text, encoding, warnings = decode_text("café — naïve".encode())
        assert text == "café — naïve" and encoding == "utf-8" and warnings == ()

    def test_utf8_bom_is_stripped_and_named(self) -> None:
        text, encoding, _ = decode_text(b"\xef\xbb\xbfhello")
        assert text == "hello" and encoding == "utf-8-sig"

    def test_utf16_bom(self) -> None:
        text, encoding, _ = decode_text("héllo".encode("utf-16"))
        assert text == "héllo" and encoding == "utf-16"

    def test_utf32_bom_wins_over_utf16(self) -> None:
        text, encoding, _ = decode_text("hi".encode("utf-32"))
        assert text == "hi" and encoding == "utf-32"

    def test_invalid_utf8_falls_back_to_latin1_with_disclosed_warning(self) -> None:
        text, encoding, warnings = decode_text(b"caf\xe9 fait \xff")
        assert text == "café fait ÿ" and encoding == "latin-1"
        assert warnings == ("Bytes are not valid UTF-8; decoded as Latin-1.",)


class TestMarkdownTitle:
    def test_first_atx_heading_wins(self) -> None:
        assert markdown_title("preamble\n\n# Research Notes ##\n\nbody\n") == "Research Notes"

    def test_no_heading_stays_none(self) -> None:
        assert markdown_title("no heading here\n## not h1\n") is None
        assert markdown_title("") is None


class TestTextFamilyParser:
    def test_txt_is_raw_text_with_no_title(self) -> None:
        result = extract_text_family(b"# not a title in txt\nbody", "text")
        assert result.text == "# not a title in txt\nbody"
        assert result.document_title is None
        assert result.embedded_metadata == {}

    def test_csv_and_json_are_raw_text_only(self) -> None:
        csv_result = extract_text_family(b"a,b\n1,2\n", "csv")
        assert csv_result.text == "a,b\n1,2\n" and csv_result.embedded_metadata == {}
        json_result = extract_text_family(b'{"a": [1, 2]}', "json")
        assert json_result.text == '{"a": [1, 2]}' and json_result.embedded_metadata == {}

    def test_engine_reports_the_decoding_used(self) -> None:
        result = extract_text_family(b"\xff\xfeh\x00i\x00", "text")
        assert result.engine.startswith("stdlib-text") and "(utf-16)" in result.engine


class TestPdfParser:
    def test_text_pages_and_full_docinfo(self) -> None:
        result = PdfParser().parse(
            make_pdf_bytes("Hello Intake M2 world", title="Spec Paper", author="A. Uthor")
        )
        assert result.text == "Hello Intake M2 world"
        assert result.page_count == 1
        assert result.document_title == "Spec Paper"
        assert result.author == "A. Uthor"
        assert result.created_at == "2024-01-02T03:04:05+00:00"
        assert result.modified_at == "2024-03-04T05:06:07+00:00"
        assert result.engine.startswith("pypdf ")
        assert result.embedded_metadata.get("Title") == "Spec Paper"
        assert result.warnings == ()

    def test_missing_docinfo_fields_stay_none(self) -> None:
        result = PdfParser().parse(
            make_pdf_bytes("bare", title=None, author=None, creation=None, modified=None)
        )
        assert result.document_title is None
        assert result.author is None
        assert result.created_at is None
        assert result.modified_at is None
        assert "Title" not in result.embedded_metadata
        assert "Author" not in result.embedded_metadata

    def test_corrupt_pdf_raises_factual_error(self) -> None:
        with pytest.raises(ExtractionFailure, match="PDF could not be parsed"):
            PdfParser().parse(b"%PDF-1.4 fake")

    def test_garbage_bytes_raise(self) -> None:
        with pytest.raises(ExtractionFailure):
            PdfParser().parse(b"\x00\x01\x02\x03")


class TestDocxParser:
    def test_paragraphs_and_core_properties(self) -> None:
        data = make_docx_bytes(
            ["First paragraph of the letter.", "Second paragraph here."],
            title="Grant Letter",
            author="B. Writer",
            subject="Funding",
        )
        result = DocxParser().parse(data)
        assert result.text == "First paragraph of the letter.\nSecond paragraph here."
        assert result.document_title == "Grant Letter"
        assert result.author == "B. Writer"
        assert result.created_at is not None and result.modified_at is not None
        assert result.embedded_metadata.get("subject") == "Funding"
        assert result.page_count is None  # OOXML carries none — never fabricated
        assert result.engine.startswith("python-docx ")

    def test_blank_document_reports_only_what_the_container_stamps(self) -> None:
        # python-docx's default template stamps author/comments/revision and
        # template dates — the adapter reports the container verbatim (the
        # honesty contract cuts both ways: no hiding, no inventing).
        result = DocxParser().parse(make_docx_bytes([]))
        assert result.text == ""
        assert result.document_title is None  # template leaves title empty
        assert result.author == "python-docx"
        assert result.created_at is not None and result.modified_at is not None
        assert result.embedded_metadata["revision"] == "1"
        assert result.page_count is None

    def test_corrupt_docx_raises_factual_error(self) -> None:
        with pytest.raises(ExtractionFailure, match="DOCX could not be parsed"):
            DocxParser().parse(b"PK\x03\x04zip-data")


class TestContractShapes:
    def test_preview_limit_is_500_chars(self) -> None:
        assert PREVIEW_LIMIT == 500

    def test_counts_are_defined_over_the_exact_text(self) -> None:
        # The mapping the service persists: len(text) / len(text.split()).
        text = "one  two\nthree\n"
        assert len(text) == 15 and len(text.split()) == 3
