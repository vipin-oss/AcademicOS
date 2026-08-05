"""ExtractionService — the M2 extraction step the IntakeRunner calls.

Orchestration only; parsing lives behind the ``DocumentParser`` port
(infrastructure adapters). The contract with the runner:

1. Read the *staged* blob through the storage port (never the source again),
   and re-verify its SHA-256 against the M1 hash record before parsing —
   extracting corrupted staging is an item error, never silent.
2. Pick the parser from the deterministic extension table. Anything outside
   the table is ``ExtractionStatus.UNSUPPORTED`` — recorded honestly, no text
   blob written, the pipeline continues unfailed.
3. Persist the **text** as a blob under ``intake-extracted/`` and the
   **descriptor** as item metadata — always separate stores.
4. Idempotent: re-running the step rewrites the exact same text key with the
   exact same descriptor, like the M1 stage step.

No sessions, no relationships, no objects are created here. Extraction never
classifies, never routes, and never touches Documents/Publications/Projects.
"""
from __future__ import annotations

from app.application.dtos.extraction import (
    INTAKE_EXTRACTION_ACTOR,
    PREVIEW_LIMIT,
    ExtractionDescriptor,
    ExtractionStatus,
    format_of,
)
from app.application.dtos.intake import (
    KEY_EXTENSION,
    KEY_EXTRACTED_KEY,
    KEY_EXTRACTION,
    KEY_RELATIVE_PATH,
    KEY_SHA256,
    KEY_STAGED_KEY,
    json_decode,
    json_encode,
)
from app.application.intake.pipeline import (
    ItemStageError,
    digest_of,
    extracted_key_for,
    utcnow_iso,
)
from app.application.ports.document_parser import DocumentParsers, ExtractionFailure
from app.application.ports.file_storage import FileStorage
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, Provenance
from app.domain.value_objects.metadata import MetadataEntry


def _put(item: UniversalObject, key: str, value: str) -> None:
    """Extraction writes are system facts: L1 layer, SYSTEM provenance."""

    item.set_metadata(
        MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor=INTAKE_EXTRACTION_ACTOR,
    )


class ExtractionService:
    """Stateless orchestrator over the parser registry — thread-safe."""

    def __init__(self, parsers: DocumentParsers) -> None:
        self._parsers = parsers

    def extract_item(
        self, item: UniversalObject, storage: FileStorage, *, session_id: str
    ) -> dict:
        """Run the M2 extraction step for one item; returns the stage record.

        Raises ``ItemStageError`` (never leaks adapter internals) so the
        runner keeps per-item isolation: one corrupt file -> one item error.
        """

        rel = item.metadata.get_value(KEY_RELATIVE_PATH) or item.title
        staged_key = item.metadata.get_value(KEY_STAGED_KEY)
        if not staged_key or not storage.exists(staged_key):
            raise ItemStageError("Staged copy is missing; the stage step must rerun.")
        try:
            blob = storage.read(staged_key)
        except Exception as exc:
            raise ItemStageError(f"Cannot read the staged copy: {exc}.") from exc

        # Integrity re-hash: the exact staged bytes are what gets extracted.
        sha256 = digest_of(blob)
        expected = item.metadata.get_value(KEY_SHA256)
        if expected and sha256 != expected:
            raise ItemStageError("Integrity check failed: staged bytes changed after hashing.")

        # M2.3 resume discipline: an extraction already recorded for THESE
        # exact bytes is completed work — the queue never restarts it. The
        # crash/heal seam: a descriptor claiming text whose blob is gone is a
        # partial earlier run; fall through and redo it properly.
        existing = self._current_descriptor(item)
        if existing is not None and existing.get("sha256") == sha256:
            status_word = existing.get("status")
            text_key_recorded = existing.get("text_key")
            if status_word == ExtractionStatus.UNSUPPORTED.value or (
                status_word == ExtractionStatus.EXTRACTED.value
                and isinstance(text_key_recorded, str)
                and text_key_recorded
                and storage.exists(text_key_recorded)
            ):
                return {"reused": True, "status": status_word}

        extension = item.metadata.get_value(KEY_EXTENSION) or ""
        format_name = format_of(extension)
        if format_name is None:
            descriptor = ExtractionDescriptor(
                status=ExtractionStatus.UNSUPPORTED.value,
                sha256=sha256,
                extracted_at=utcnow_iso(),
            )
            self._persist(item, descriptor)
            return {
                "status": ExtractionStatus.UNSUPPORTED.value,
                "extension": extension or "(none)",
            }

        parser = self._parsers.get(format_name)
        if parser is None:
            raise ItemStageError(f"No extraction parser registered for format {format_name!r}.")
        try:
            result = parser.parse(blob)
        except ExtractionFailure as exc:
            raise ItemStageError(str(exc)) from exc
        except Exception as exc:  # adapters must not leak exotic failures
            raise ItemStageError(f"Extraction crashed ({type(exc).__name__}: {exc}).") from exc

        text_key = extracted_key_for(session_id, rel)
        raw = result.text.encode("utf-8")
        try:
            storage.save(text_key, raw)
        except Exception as exc:
            raise ItemStageError(f"Cannot persist the extracted text: {exc}.") from exc

        descriptor = ExtractionDescriptor(
            status=ExtractionStatus.EXTRACTED.value,
            engine=result.engine,
            format=format_name,
            sha256=sha256,
            page_count=result.page_count,
            word_count=len(result.text.split()),
            character_count=len(result.text),
            document_title=result.document_title,
            author=result.author,
            created_at=result.created_at,
            modified_at=result.modified_at,
            embedded_metadata=result.embedded_metadata,
            text_key=text_key,
            text_bytes=len(raw),
            preview_text=result.text[:PREVIEW_LIMIT],
            warnings=result.warnings,
            extracted_at=utcnow_iso(),
        )
        self._persist(item, descriptor)
        record: dict = {
            "status": ExtractionStatus.EXTRACTED.value,
            "format": format_name,
            "engine": result.engine,
            "words": descriptor.word_count,
            "chars": descriptor.character_count,
            "text_key": text_key,
        }
        if result.page_count is not None:
            record["pages"] = result.page_count
        if result.document_title:
            record["title"] = result.document_title
        if result.warnings:
            record["warnings"] = list(result.warnings)
        return record

    @staticmethod
    def _current_descriptor(item: UniversalObject) -> dict | None:
        """The decoded descriptor on record (``None`` when absent/malformed)."""

        data = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        return data if isinstance(data, dict) else None

    @staticmethod
    def _persist(item: UniversalObject, descriptor: ExtractionDescriptor) -> None:
        _put(item, KEY_EXTRACTION, json_encode(descriptor.to_dict()))
        _put(item, KEY_EXTRACTED_KEY, descriptor.text_key or "")
