"""L2 format detector (ADR-031).

Deterministic magic-byte / signature checks cross-checked against the claimed
extension (from ``SUPPORTED_FORMATS``). Used for honest MIME/content mismatch
recording, never to silently re-route the parser (no content-guessing AI).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.extraction import format_of
from app.domain.value_objects.source import MediaKind


@dataclass(frozen=True)
class FormatProbe:
    extension: str
    family: str | None
    media_kind: MediaKind
    magic_match: bool
    detected_family: str | None
    mismatch_warning: str | None = None


#: magic-bytes -> format family (deterministic, small, conservative).
_MAGIC: dict[str, str] = {
    b"%PDF-": "pdf",
    b"PK\x03\x04": None,  # ZIP/OOXML/PPTX/DOCX/XLSX disambiguated by extension
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
    b"II*\x00": "tiff",
    b"MM\x00*": "tiff",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"RIFF": "webp",
    b"BM": "bmp",
}

#: OOXML internal signature: a PK zip whose [Content_Types].xml exists.
_OOXML_TYPES = b"[Content_Types].xml"


def _peek(data: bytes, n: int = 64) -> bytes:
    return data[:n]


def detect(data: bytes, extension: str) -> FormatProbe:
    """Probe a blob against its claimed extension.

    ``family`` is from ``SUPPORTED_FORMATS``; ``media_kind`` from ``MediaKind``.
    ``magic_match``/``detected_family`` record the magic check; a mismatch is
    surfaced as ``mismatch_warning`` (honest, non-blocking).
    """
    ext = (extension or "").lower().lstrip(".")
    family = format_of(ext)
    media_kind = MediaKind.from_extension(ext)
    head = _peek(data)

    detected: str | None = None
    for magic, fam in _MAGIC.items():
        if head.startswith(magic):
            detected = fam
            break
    # OOXML (docx/xlsx/pptx) are PK zips containing [Content_Types].xml
    if detected is None and head.startswith(b"PK\x03\x04"):
        if _OOXML_TYPES in data[:1_000_000]:
            ooxml_family = _ooxml_family(extension, family)
            detected = ooxml_family
        else:
            detected = "zip"

    magic_match = detected == family or _is_compatible(extension, detected)
    warning = None
    if family is not None and detected is not None and not magic_match:
        warning = (
            f"Content magic ({detected}) does not match extension (.{ext}); "
            "parser not re-routed."
        )
    return FormatProbe(
        extension=ext,
        family=family,
        media_kind=media_kind,
        magic_match=magic_match,
        detected_family=detected,
        mismatch_warning=warning,
    )


def _ooxml_family(extension: str, family: str | None) -> str:
    # disambiguate by extension; default to family if it is already a family
    if extension in {"docx", "xlsx", "pptx"}:
        return extension
    return family or "zip"


def _is_compatible(extension: str, detected: str | None) -> bool:
    if detected is None:
        return False
    compat = {
        "pdf": {"pdf"},
        "png": {"png", "image"},
        "jpeg": {"jpeg", "jpg", "image"},
        "webp": {"webp", "image"},
        "tiff": {"tiff", "tif", "image"},
        "bmp": {"bmp", "image"},
        "gif": {"gif", "image"},
        "zip": {"zip", "docx", "xlsx", "pptx", "package"},
    }
    return detected in compat.get(extension, {extension})
