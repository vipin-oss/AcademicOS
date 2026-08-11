"""Unit tests: the document-content projection is written at intake commit (M27).

The Commit Engine is the single document creator; when a content store is
wired, committing an extracted item writes the searchable content row from
the extracted-text blob (the blob stays authoritative). Without a wired
store the commit degrades exactly as before (no content row).
"""
from __future__ import annotations

import pytest

from app.application.dtos.intake import (
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_PROPOSAL,
    KEY_SESSION_ID,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.application.intake.commit_engine import CommitEngineService
from app.application.ports.document_content_store import DocumentContentStore
from app.application.ports.file_storage import FileStorage
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

from app.tests.unit.test_intake_commit import (
    InMemoryFileStorage,
    InMemoryObjectRepository,
    _awaiting_item,
    _completed_session,
    _entry,
)


class RecordingContentStore(DocumentContentStore):
    """Records upserts/deletes instead of persisting (unit-level assertion)."""

    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.deletes: list[str] = []

    def upsert(self, *, object_id, version, content_text, source_item_id) -> None:
        self.upserts.append(
            {
                "object_id": object_id,
                "version": version,
                "content_text": content_text,
                "source_item_id": source_item_id,
            }
        )

    def delete(self, object_id) -> None:
        self.deletes.append(object_id)

    def get_content(self, object_id) -> str | None:
        for row in reversed(self.upserts):
            if row["object_id"] == object_id:
                return row["content_text"]
        return None


def _item_with_text_key(repo, session, storage, text: str) -> UniversalObject:
    # The commit gate reads the staged blob at the fixture's KEY_STAGED_KEY
    # and the extraction descriptor's text_key for the content projection.
    storage.save("staging/session/report.pdf", text.encode("utf-8"))
    item = _awaiting_item(
        repo,
        session,
        extraction=json_encode(
            {
                "status": "extracted",
                "format": "txt",
                "engine": "text",
                "text_key": "staging/session/report.pdf",
            }
        ),
        extension="txt",
    )
    # reviewed proposal (commit gate)
    item.set_metadata(
        MetadataEntry(
            KEY_PROPOSAL,
            json_encode({"title": "Lab Report", "document_type": "report"}),
            MetadataLayer.L5_INFERRED,
            Provenance.INFERRED,
        ),
        actor="intake",
    )
    repo.save(item)
    return item


def _engine(repo, storage, content_store=None) -> CommitEngineService:
    return CommitEngineService(repo, storage, content_store=content_store)


def test_commit_writes_content_projection_from_text_blob():
    repo = InMemoryObjectRepository()
    storage = InMemoryFileStorage()
    store = RecordingContentStore()
    session = _completed_session(repo)
    item = _item_with_text_key(repo, session, storage, "quantum entanglement results section")

    out = _engine(repo, storage, store).commit_item(str(item.id), actor="tester")

    assert out.document_id
    assert store.upserts, "content row must be written on commit"
    row = store.upserts[0]
    assert row["object_id"] == out.document_id
    assert row["source_item_id"] == str(item.id)
    assert "quantum entanglement" in row["content_text"]
    assert row["version"] >= 1


def test_commit_without_store_degrades_gracefully():
    """No wired store = previous behavior: commit succeeds, no content row."""
    repo = InMemoryObjectRepository()
    storage = InMemoryFileStorage()
    session = _completed_session(repo)
    item = _item_with_text_key(repo, session, storage, "some text")

    out = _engine(repo, storage).commit_item(str(item.id), actor="tester")

    assert out.document_id  # commit still succeeds
