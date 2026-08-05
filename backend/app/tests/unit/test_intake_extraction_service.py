"""Unit tests for ExtractionService — the M2 runner-facing step.

In-memory fakes only (ports, never frameworks). The service contract under
test: staged-blob integrity re-hash, deterministic dispatch, UNSUPPORTED as a
record rather than a failure, separate text/descriptor stores, idempotency,
and per-item error mapping via ``ItemStageError``.
"""
from __future__ import annotations

import hashlib

import pytest

from app.application.dtos.extraction import ExtractionStatus
from app.application.dtos.intake import (
    KEY_EXTRACTED_KEY,
    KEY_EXTRACTION,
    json_decode,
)
from app.application.intake.extraction.service import ExtractionService
from app.application.intake.pipeline import ItemStageError, extracted_key_for
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.infrastructure.extraction import build_document_parsers
from app.tests.unit.extraction_fixtures import make_docx_bytes, make_pdf_bytes

SID = "obj:intake_session:TESTSID00001"


class FakeStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.blobs[key] = bytes(content)

    def read(self, key: str) -> bytes:
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


def _mk_item(rel: str, extension: str, staged_key: str | None, blob: bytes | None) -> UniversalObject:
    entries = [
        ("intake.relative_path", rel),
        ("intake.extension", extension),
    ]
    if staged_key is not None and blob is not None:
        entries += [
            ("intake.staged_key", staged_key),
            ("intake.sha256", hashlib.sha256(blob).hexdigest()),
        ]
    return UniversalObject.create(
        object_type=ObjectType.INTAKE_ITEM,
        title=rel.rsplit("/", 1)[-1],
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=tuple(
                MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)
                for k, v in entries
            )
        ),
    )


def _seed(storage: FakeStorage, rel: str, extension: str, blob: bytes) -> UniversalObject:
    staged_key = f"intake/{SID.replace(':', '_')}/{rel}"
    storage.save(staged_key, blob)
    return _mk_item(rel, extension, staged_key, blob)


class TestSupportedExtraction:
    def test_full_descriptor_and_separate_text_blob(self) -> None:
        storage = FakeStorage()
        blob = make_pdf_bytes("Hello Intake M2 world", title="Spec Paper", author="A. Uthor")
        item = _seed(storage, "docs/paper one.pdf", "pdf", blob)

        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)

        assert record["status"] == "extracted"
        assert record["format"] == "pdf"
        assert record["words"] == 4 and record["chars"] == 21
        assert record["pages"] == 1 and record["title"] == "Spec Paper"
        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        assert descriptor["status"] == "extracted"
        assert descriptor["sha256"] == hashlib.sha256(blob).hexdigest()
        assert descriptor["word_count"] == 4 and descriptor["character_count"] == 21
        assert descriptor["page_count"] == 1
        assert descriptor["document_title"] == "Spec Paper"
        assert descriptor["author"] == "A. Uthor"
        assert descriptor["created_at"] == "2024-01-02T03:04:05+00:00"
        assert descriptor["modified_at"] == "2024-03-04T05:06:07+00:00"
        assert descriptor["embedded_metadata"]["Title"] == "Spec Paper"
        assert descriptor["preview_text"] == "Hello Intake M2 world"
        assert descriptor["text_bytes"] == len(b"Hello Intake M2 world")
        assert descriptor["warnings"] == []
        assert descriptor["extracted_at"]

        text_key = item.metadata.get_value(KEY_EXTRACTED_KEY)
        assert text_key == extracted_key_for(SID, "docs/paper one.pdf")
        assert text_key == descriptor["text_key"]
        assert storage.blobs[text_key] == b"Hello Intake M2 world"
        # Staged source untouched; the two stores stay separate.
        assert storage.blobs[extracted_key_for(SID, "docs/paper one.pdf")] == b"Hello Intake M2 world"
        assert storage.blobs[f"intake/{SID.replace(':', '_')}/docs/paper one.pdf"] == blob

    def test_docx_descriptor_has_no_fabricated_page_count(self) -> None:
        storage = FakeStorage()
        blob = make_docx_bytes(["alpha beta", "gamma"], title="Grant Letter", author="B. Writer")
        item = _seed(storage, "letter.docx", "docx", blob)
        ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)
        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        assert descriptor["status"] == "extracted"
        assert descriptor["page_count"] is None
        assert descriptor["word_count"] == 3
        assert descriptor["preview_text"] == "alpha beta\ngamma"
        assert descriptor["embedded_metadata"].get("subject") is None

    def test_preview_is_exactly_the_first_500_characters(self) -> None:
        storage = FakeStorage()
        blob = ("word " * 150 + "\nend").encode()  # 755+ chars
        item = _seed(storage, "long.txt", "txt", blob)
        ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)
        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        assert descriptor["preview_text"] == blob.decode()[:500]
        assert len(descriptor["preview_text"]) == 500
        assert descriptor["character_count"] == len(blob.decode())
        assert storage.blobs[item.metadata.get_value(KEY_EXTRACTED_KEY)] == blob

    def test_latin1_fallback_warns_but_still_extracts(self) -> None:
        storage = FakeStorage()
        item = _seed(storage, "legacy.txt", "txt", b"caf\xe9")
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)
        assert record["warnings"] == ["Bytes are not valid UTF-8; decoded as Latin-1."]
        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        assert descriptor["preview_text"] == "café"
        assert "latin-1" in descriptor["engine"]


class TestUnsupportedFormats:
    @pytest.mark.parametrize("extension", ["png", "xlsx", "zip", ""])
    def test_unsupported_is_a_record_not_a_failure(self, extension: str) -> None:
        storage = FakeStorage()
        rel = f"img.{extension}" if extension else "noext"
        item = _seed(storage, rel, extension, b"\x89PNG\r\n\x1a\nDATA")
        record = ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)

        assert record["status"] == ExtractionStatus.UNSUPPORTED.value
        descriptor = json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
        assert descriptor["status"] == "unsupported"
        assert descriptor["word_count"] is None and descriptor["character_count"] is None
        assert descriptor["page_count"] is None and descriptor["preview_text"] is None
        assert descriptor["text_key"] is None and descriptor["engine"] is None
        assert descriptor["sha256"]  # integrity fact still recorded
        assert item.metadata.get_value(KEY_EXTRACTED_KEY) == ""
        # Nothing written anywhere but metadata.
        assert list(storage.blobs) == [f"intake/{SID.replace(':', '_')}/{rel}"]


class TestIntegrityAndFailures:
    def test_mutated_staging_after_hashing_is_an_item_error(self) -> None:
        storage = FakeStorage()
        blob = make_pdf_bytes("original")
        item = _seed(storage, "paper.pdf", "pdf", blob)
        storage.save(f"intake/{SID.replace(':', '_')}/paper.pdf", b"tampered")
        with pytest.raises(ItemStageError, match="changed after hashing"):
            ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)
        assert item.metadata.get_value(KEY_EXTRACTION) is None  # nothing persisted

    def test_missing_staged_blob_is_an_item_error(self) -> None:
        item = _mk_item("gone.pdf", "pdf", None, None)
        with pytest.raises(ItemStageError, match="Staged copy is missing"):
            ExtractionService(build_document_parsers()).extract_item(item, FakeStorage(), session_id=SID)

    def test_corrupt_supported_file_maps_to_item_stage_error(self) -> None:
        storage = FakeStorage()
        item = _seed(storage, "broken.pdf", "pdf", b"%PDF-1.4 fake")
        with pytest.raises(ItemStageError, match="PDF could not be parsed"):
            ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=SID)
        assert item.metadata.get_value(KEY_EXTRACTION) is None
        assert item.metadata.get_value(KEY_EXTRACTED_KEY) is None

    def test_extraction_is_idempotent(self) -> None:
        storage = FakeStorage()
        item = _seed(storage, "note.md", "md", b"# T\n\nbody")
        service = ExtractionService(build_document_parsers())
        service.extract_item(item, storage, session_id=SID)
        first = item.metadata.get_value(KEY_EXTRACTION)
        first_key = item.metadata.get_value(KEY_EXTRACTED_KEY)
        service.extract_item(item, storage, session_id=SID)  # rerun (resume path)
        assert item.metadata.get_value(KEY_EXTRACTED_KEY) == first_key
        assert json_decode(item.metadata.get_value(KEY_EXTRACTION), None)["text_key"] == first_key
        assert json_decode(first, None)["status"] == "extracted"
        assert storage.blobs[first_key] == b"# T\n\nbody"
