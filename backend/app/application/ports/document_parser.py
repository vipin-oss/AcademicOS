"""Port: deterministic document parsing (Intake M2 Part 1).

The application layer declares WHAT a parser is; the infrastructure layer
provides adapters around the concrete binary readers (pypdf, python-docx)
plus the stdlib text-family parser. Application code never imports those
libraries itself — the same port doctrine as ``ports/file_storage.py``.

Contract:

- one parser per M2 parser family, selected by the deterministic extension
  table in ``dtos/extraction.SUPPORTED_FORMATS`` (never content guessing);
- ``parse`` returns an :class:`ExtractionResult` with exactly what the file
  contains — absent fields stay ``None``/empty, never inferred;
- unreadable/corrupt/encrypted input raises :class:`ExtractionFailure` with a
  factual, user-facing message (it is surfaced verbatim on the item's error
  record).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from app.application.dtos.extraction import ExtractionResult


class ExtractionFailure(Exception):
    """A supported document could not be parsed by its adapter."""


@runtime_checkable
class DocumentParser(Protocol):
    """One deterministic parser for one M2 parser family."""

    @property
    def format_name(self) -> str:
        """The family key from ``SUPPORTED_FORMATS`` this parser serves."""
        ...

    def parse(self, data: bytes) -> ExtractionResult:
        """Deterministic bytes-in/result-out extraction."""
        ...


DocumentParsers = Mapping[str, "DocumentParser"]
"""The composition unit handed to application services: family -> parser."""
