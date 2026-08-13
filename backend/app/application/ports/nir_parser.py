"""Application port: structured parser (L2, ADR-028).

One deterministic engine adapter per media kind/format family. Produces a
transient ``NirDocument`` (ADR-028) — the engine output contract. Infrastructure
provides the adapters (pdfplumber/openpyxl/python-pptx/Pillow); application
never imports those libraries.
"""

from __future__ import annotations

import abc

from app.application.dtos.nir import NirDocument


class NirParseError(Exception):
    """A supported source could not be parsed by its engine adapter."""


class NirParser(abc.ABC):
    @property
    @abc.abstractmethod
    def format_name(self) -> str:
        """The family key this parser serves (from SUPPORTED_FORMATS)."""

    @abc.abstractmethod
    def parse(self, data: bytes, *, source_id: str, version: int) -> NirDocument:
        """Deterministic bytes-in / NirDocument-out extraction.

        Raises ``NirParseError`` for corrupt/unreadable input (with a factual
        message). Unsupported values are represented honestly, never guessed.
        """
