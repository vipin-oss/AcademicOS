"""Extraction Engine (v2 — Intake M2 Part 1) — boundary DTOs.

M2 turns staged bytes into deterministic, engine-extracted content. Pure
boundary shapes — no framework imports, mirroring ``dtos/intake.py`` doctrine.

What M2 extracts is *never* inferred or fabricated:

- structural fields (filename/ext/mime/size/sha256) come from the M1 item
  record plus an integrity re-hash of the staged blob;
- counts are computed over the exact extracted text
  (``len(text)`` / ``len(text.split())`` — the transparent baseline);
- document title, author, creation/modification dates and embedded metadata
  come only from metadata containers *inside* the file (PDF docinfo, DOCX
  core properties); absent containers stay ``None`` / ``{}``;
- raw extracted text and its first-500-character preview are engine output,
  never summarised, never AI-touched.

The persistent **descriptor** lives as one JSON-encoded metadata entry on the
intake item; the extracted **text** lives as a separate storage blob under the
``intake-extracted/`` prefix — metadata and text stay separate, and staged
files are never overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

INTAKE_EXTRACTION_ACTOR = "intake-extraction"
"""Audit actor recorded for M2 extraction writes (distinct from M1's actor)."""

EXTRACTION_PREFIX = "intake-extracted"
"""Top-level storage-key prefix for extracted text blobs.

Deliberately separate from the M1 ``intake/`` staging prefix so an extracted
text blob can never collide with — let alone overwrite — a staged source.
"""

EXTRACTION_TEXT_SUFFIX = ".txt"
"""Suffix appended to every extracted text key (extract type is always text)."""

# NOTE: the metadata keys (``intake.extraction`` / ``intake.extracted_key``)
# live in ``dtos/intake.py`` with every other ``intake.*`` key — one registry.


class ExtractionStatus(str, Enum):
    """Outcome of the extraction step for one staged file."""

    EXTRACTED = "extracted"
    UNSUPPORTED = "unsupported"


#: Deterministic engine table. The *extension* (already normalised by the M1
#: enumeration) selects the parser family — never content guessing, never AI.
#: Anything outside this table is ``ExtractionStatus.UNSUPPORTED``.
SUPPORTED_FORMATS: dict[str, str] = {
    "pdf": "pdf",
    "docx": "docx",
    "txt": "text",
    "md": "markdown",
    "markdown": "markdown",
    "csv": "csv",
    "json": "json",
}

PREVIEW_LIMIT = 500
"""The preview contract: exactly the first 500 characters of extracted text."""


def format_of(extension: str) -> str | None:
    """Map a normalised extension (lower-case, no dot) to a parser family."""

    return SUPPORTED_FORMATS.get(extension.lower())


@dataclass(frozen=True)
class ExtractionResult:
    """What one engine could honestly pull out of one byte string."""

    text: str
    engine: str
    page_count: int | None = None
    document_title: str | None = None
    author: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    embedded_metadata: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractionDescriptor:
    """The persisted summary of one extraction run (metadata side).

    Serialised to the item as compact sorted JSON via ``json_encode`` — the
    same single-JSON-string doctrine every other intake key follows.
    """

    status: str
    engine: str | None = None
    format: str | None = None
    sha256: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    character_count: int | None = None
    document_title: str | None = None
    author: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    embedded_metadata: dict[str, str] = field(default_factory=dict)
    text_key: str | None = None
    text_bytes: int | None = None
    preview_text: str | None = None
    warnings: tuple[str, ...] = ()
    extracted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "engine": self.engine,
            "format": self.format,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "document_title": self.document_title,
            "author": self.author,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "embedded_metadata": self.embedded_metadata,
            "text_key": self.text_key,
            "text_bytes": self.text_bytes,
            "preview_text": self.preview_text,
            "warnings": list(self.warnings),
            "extracted_at": self.extracted_at,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> ExtractionDescriptor | None:
        if not isinstance(data, dict) or data.get("status") not in (
            ExtractionStatus.EXTRACTED.value,
            ExtractionStatus.UNSUPPORTED.value,
        ):
            return None
        warnings = data.get("warnings")
        embedded = data.get("embedded_metadata")
        return ExtractionDescriptor(
            status=str(data.get("status")),
            engine=_opt_str(data.get("engine")),
            format=_opt_str(data.get("format")),
            sha256=_opt_str(data.get("sha256")),
            page_count=_opt_int(data.get("page_count")),
            word_count=_opt_int(data.get("word_count")),
            character_count=_opt_int(data.get("character_count")),
            document_title=_opt_str(data.get("document_title")),
            author=_opt_str(data.get("author")),
            created_at=_opt_str(data.get("created_at")),
            modified_at=_opt_str(data.get("modified_at")),
            embedded_metadata=(
                {str(k): str(v) for k, v in embedded.items()}
                if isinstance(embedded, dict)
                else {}
            ),
            text_key=_opt_str(data.get("text_key")),
            text_bytes=_opt_int(data.get("text_bytes")),
            preview_text=_opt_str(data.get("preview_text")),
            warnings=tuple(str(w) for w in warnings) if isinstance(warnings, list) else (),
            extracted_at=_opt_str(data.get("extracted_at")),
        )


def _opt_str(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _opt_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
