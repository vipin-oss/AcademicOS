"""Stdlib text-family parsing (TXT / Markdown / CSV / JSON) — M2.

Pure stdlib, so it lives in the application layer directly (the PDF/DOCX
readers are infrastructure adapters behind ``ports/document_parser.py``).

Raw text IS the honest extraction for these formats: no rendering, no
normalisation, no schema guessing. The one convenience signal allowed:
Markdown's first ATX ``#`` heading doubles as the document title — the only
title the format carries.
"""
from __future__ import annotations

import re

from app.application.dtos.extraction import ExtractionResult

TEXT_ENGINE = "stdlib-text 1.0"

_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)

_MD_HEADING = re.compile(r"^#[ \t]+(.+?)[ \t#]*$")


def decode_text(data: bytes) -> tuple[str, str, tuple[str, ...]]:
    """Deterministic decoding ladder: BOM first, then strict UTF-8, then a
    documented Latin-1 fallback (every byte maps, so decoding can never crash
    — and the substitution is always disclosed in the warnings)."""

    for signature, encoding in _BOMS:
        if data.startswith(signature):
            return data.decode(encoding), encoding, ()
    try:
        return data.decode("utf-8"), "utf-8", ()
    except UnicodeDecodeError:
        return (
            data.decode("latin-1"),
            "latin-1",
            ("Bytes are not valid UTF-8; decoded as Latin-1.",),
        )


def markdown_title(text: str) -> str | None:
    """First ATX ``#`` heading, or ``None`` when the document has none."""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        match = _MD_HEADING.match(stripped)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def extract_text_family(data: bytes, format_name: str) -> ExtractionResult:
    """TXT/Markdown/CSV/JSON bytes -> honest raw-text result."""

    text, encoding, warnings = decode_text(data)
    title = markdown_title(text) if format_name == "markdown" else None
    return ExtractionResult(
        text=text,
        engine=f"{TEXT_ENGINE} ({encoding})",
        document_title=title,
        warnings=warnings,
    )


class TextFamilyParser:
    """Port adapter for the stdlib text families (one instance per family)."""

    def __init__(self, format_name: str) -> None:
        if format_name not in ("text", "markdown", "csv", "json"):
            raise ValueError(f"Not a text-family format: {format_name!r}")
        self._format_name = format_name

    @property
    def format_name(self) -> str:
        return self._format_name

    def parse(self, data: bytes) -> ExtractionResult:
        return extract_text_family(data, self._format_name)
