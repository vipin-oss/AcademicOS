"""Format-agnostic SOURCE contract (L1).

The Source is the unit of ingestion that L2 engines write into and that every
span / claim / CDM artifact traces back to. It is deliberately NOT tied to a
specific file type (PDF, DOCX, ...): a Source is whatever the user uploaded or
a member of a package, described by a media kind and bound to the original
blob for evidence.

Distinctions the contract preserves (never conflates):

- ``source identity``  -> the ``document`` UniversalObject id (one per upload /
  package member)
- ``file identity``    -> ``intake.sha256`` (raw bytes) OR content-hash
  (normalized text); the registry keeps canonical-duplicate links
- ``file version``     -> ``object_versions`` immutable snapshot + a version
  number on the object
- ``media / container kind`` -> ``MediaKind`` (below), independent of format
- ``original blob / evidence`` -> a stable storage key via the ``FileStorage``
  port so the original page/image always remains recoverable as evidence
- ``provenance``       -> engine + engine_version + provenance enum
- ``processing / extraction state`` -> intake stage + needs_ocr honesty signal

L1 defines the contract; it does NOT implement any parser/OCR/vision engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.value_objects.enums import Provenance


class MediaKind(str, Enum):
    """The high-level media category of a source, independent of parser.

    Engines (L2) plug adapters per media kind; the knowledge model does not
    special-case any concrete format.
    """

    TEXT_LAYOUT = "text_layout"          # PDF, DOC/DOCX, PPT/PPTX (text-bearing pages/slides)
    SPREADSHEET = "spreadsheet"           # XLS/XLSX, CSV (cell grid)
    RASTER_IMAGE = "raster_image"         # JPG/JPEG, PNG, WebP, TIFF, screenshots, scanned images
    SLIDES = "slides"                     # PPT/PPTX as slide sequence
    PLAIN_TEXT = "plain_text"             # TXT, MD, JSON
    PACKAGE = "package"                   # ZIP / archive container
    UNKNOWN = "unknown"                   # undetermined / unsupported media

    @classmethod
    def from_extension(cls, extension: str) -> MediaKind:
        """Deterministic, best-effort extension -> media kind mapping.

        This is a *convenience heuristic* for the contract layer, NOT content
        sniffing and NOT an engine. Unrecognised extensions map to UNKNOWN so
        they are surfaced honestly rather than guessed.
        """
        ext = (extension or "").lower().lstrip(".")
        if ext in {"pdf", "doc", "docx", "odt"}:
            return cls.TEXT_LAYOUT
        if ext in {"ppt", "pptx", "odp"}:
            return cls.SLIDES
        if ext in {"xls", "xlsx", "ods", "csv"}:
            return cls.SPREADSHEET
        if ext in {"jpg", "jpeg", "png", "webp", "tif", "tiff", "bmp", "gif"}:
            return cls.RASTER_IMAGE
        if ext in {"txt", "md", "markdown", "json"}:
            return cls.PLAIN_TEXT
        if ext in {"zip", "tar", "gz", "7z", "rar"}:
            return cls.PACKAGE
        return cls.UNKNOWN


@dataclass(frozen=True)
class SourceContract:
    """The immutable identity + provenance attributes of one source.

    This value object is the contract carried by derived artifacts. It is not
    a database row by itself; the ``document`` object + intake metadata are the
    authoritative storage, and this VO is the typed representation L1 services
    pass around and project onto claims / spans / CDM / ACL.
    """

    source_id: str                     # the document UniversalObject id
    media_kind: MediaKind
    blob_key: str                      # stable storage key -> original artifact (evidence)
    file_sha256: str | None = None     # raw-bytes identity (KEY_SHA256)
    content_hash: str | None = None    # normalized-text identity (document_registry)
    version: int = 1                   # object version (ADR-021 chain anchor)
    container_source_id: str | None = None  # package identity, if member of a package
    container_path: str | None = None       # path within the package (provenance)
    engine: str | None = None
    engine_version: int | None = None
    provenance: Provenance = Provenance.SYSTEM
    extraction_state: str = "unprocessed"   # intake stage / needs_ocr honesty signal
    needs_ocr: bool = False

    @property
    def is_package_member(self) -> bool:
        return self.container_source_id is not None

    def with_evidence(self, *, engine: str, engine_version: int) -> SourceContract:
        """Stamp engine provenance without mutating the original."""
        return SourceContract(
            source_id=self.source_id,
            media_kind=self.media_kind,
            blob_key=self.blob_key,
            file_sha256=self.file_sha256,
            content_hash=self.content_hash,
            version=self.version,
            container_source_id=self.container_source_id,
            container_path=self.container_path,
            engine=engine,
            engine_version=engine_version,
            provenance=self.provenance,
            extraction_state=self.extraction_state,
            needs_ocr=self.needs_ocr,
        )


# Metadata keys used to persist the source contract on the document object.
KEY_SOURCE_MEDIA_KIND = "source.media_kind"
KEY_SOURCE_BLOB_KEY = "source.blob_key"
KEY_SOURCE_CONTAINER_ID = "source.container_id"
KEY_SOURCE_CONTAINER_PATH = "source.container_path"
KEY_SOURCE_ENGINE = "source.engine"
KEY_SOURCE_ENGINE_VERSION = "source.engine_version"
KEY_SOURCE_EXTRACTION_STATE = "source.extraction_state"

__all__ = [
    "KEY_SOURCE_BLOB_KEY",
    "KEY_SOURCE_CONTAINER_ID",
    "KEY_SOURCE_CONTAINER_PATH",
    "KEY_SOURCE_ENGINE",
    "KEY_SOURCE_ENGINE_VERSION",
    "KEY_SOURCE_EXTRACTION_STATE",
    "KEY_SOURCE_MEDIA_KIND",
    "MediaKind",
    "SourceContract",
]
