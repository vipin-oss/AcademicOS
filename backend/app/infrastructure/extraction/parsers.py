"""Concrete binary readers for the M2 extraction port.

pypdf / python-docx live here — the infrastructure layer — never in the
application layer. Both adapters are deterministic: whatever the container
does not carry stays ``None``; corrupt or encrypted input raises
``ExtractionFailure`` with a factual, user-facing message.
"""
from __future__ import annotations

import io
from datetime import UTC, datetime

from app.application.dtos.extraction import ExtractionResult
from app.application.ports.document_parser import ExtractionFailure


def _iso_or_none(value: datetime | None) -> str | None:
    """ISO-8601 for real datetimes; ``None`` stays ``None`` (never invented)."""

    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _stringify(value: object) -> str | None:
    """Normalise one embedded-metadata value to a plain string (or ``None``)."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return _iso_or_none(value)
    text = str(value).strip()
    return text or None


def _docinfo_date(info: object, attribute: str) -> str | None:
    """Best-effort embedded date from pypdf's ``DocumentInformation``.

    pypdf exposes ``creation_date`` / ``modification_date`` as *properties* that
    parse the raw ``/CreationDate`` / ``/ModDate`` strings. Those properties raise
    — ``IndexError`` on an empty date string, ``ValueError`` on a malformed one —
    and a ``hasattr`` guard suppresses only ``AttributeError``, so the exception
    escaped un-wrapped and crashed the whole parse (V3 audit A2). Embedded
    metadata is best-effort: a missing or unparseable date is reported as
    ``None``, never as a fabricated value and never as a failed extraction.
    """

    try:
        value = getattr(info, attribute)
    except Exception:  # noqa: BLE001 — best-effort metadata; never fail the parse
        return None
    return _iso_or_none(value)


class PdfParser:
    """pypdf adapter: text, page count and docinfo from one PDF byte string."""

    @property
    def format_name(self) -> str:
        return "pdf"

    def parse(self, data: bytes) -> ExtractionResult:
        try:
            import pypdf
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ExtractionFailure(f"PDF engine unavailable: {exc}.") from exc

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise ExtractionFailure(
                f"PDF could not be parsed ({type(exc).__name__}: {exc})."
            ) from exc

        if reader.is_encrypted:
            raise ExtractionFailure(
                "PDF is encrypted; password-protected files are not supported yet."
            )

        try:
            page_count = len(reader.pages)
        except Exception as exc:
            raise ExtractionFailure(
                f"PDF page tree is unreadable ({type(exc).__name__}: {exc})."
            ) from exc

        parts: list[str] = []
        for index in range(page_count):
            try:
                page_text = reader.pages[index].extract_text()
            except Exception as exc:
                raise ExtractionFailure(
                    f"PDF page {index + 1} could not be parsed ({type(exc).__name__}: {exc})."
                ) from exc
            if page_text:
                parts.append(page_text)

        info = reader.metadata or {}
        embedded: dict[str, str] = {}
        for raw_key, raw_value in info.items():
            key = str(raw_key).lstrip("/")
            value = _stringify(raw_value)
            if value is not None:
                embedded[key] = value

        return ExtractionResult(
            text="\n".join(parts),
            engine=f"pypdf {pypdf.__version__}",
            page_count=page_count,
            document_title=_stringify(getattr(info, "title", None)),
            author=_stringify(getattr(info, "author", None)),
            created_at=_docinfo_date(info, "creation_date"),
            modified_at=_docinfo_date(info, "modification_date"),
            embedded_metadata=embedded,
        )


class DocxParser:
    """python-docx adapter: paragraph text and core properties.

    Page count is not recorded in the OOXML core package, so it stays
    ``None`` — reporting a fabricated number would be worse than none.
    """

    @property
    def format_name(self) -> str:
        return "docx"

    def parse(self, data: bytes) -> ExtractionResult:
        try:
            import docx
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ExtractionFailure(f"DOCX engine unavailable: {exc}.") from exc

        try:
            document = docx.Document(io.BytesIO(data))
        except Exception as exc:
            raise ExtractionFailure(
                f"DOCX could not be parsed ({type(exc).__name__}: {exc})."
            ) from exc

        props = document.core_properties
        embedded: dict[str, str] = {}
        for name in (
            "category",
            "comments",
            "content_status",
            "identifier",
            "keywords",
            "language",
            "last_modified_by",
            "subject",
            "version",
        ):
            value = _stringify(getattr(props, name, None))
            if value is not None:
                embedded[name] = value
        revision = getattr(props, "revision", None)
        if revision:
            embedded["revision"] = str(revision)

        return ExtractionResult(
            text="\n".join(paragraph.text for paragraph in document.paragraphs),
            engine=f"python-docx {docx.__version__}",
            page_count=None,
            document_title=_stringify(props.title),
            author=_stringify(props.author),
            created_at=_iso_or_none(props.created),
            modified_at=_iso_or_none(props.modified),
            embedded_metadata=embedded,
        )
