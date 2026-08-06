"""Unit tests for the Proposal Engine (Sprint-3 M2)."""
from __future__ import annotations

import pytest

from app.application.dtos.intake import (
    KEY_EXTENSION,
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_MIME_TYPE,
    KEY_PROPOSAL,
    KEY_SIZE_BYTES,
    IntakeItemStatus,
    json_encode,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.intake.proposal_engine import (
    ProposalEngineService,
    proposal_from_item,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryRepo(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[str(entity.id)] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id: ObjectId) -> bool:
        return str(id) in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(str(id), None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        return []

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return []

    def find_inbound(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return []

    def find(self, *, object_type=None, status=None, metadata_key=None,
             metadata_value=None, page=1, page_size=0, sort_by=None, order="asc"):
        return self.list()

    def count(self, *, object_type=None, status=None, metadata_key=None,
              metadata_value=None) -> int:
        return len(self.list())


def _entry(k: str, v: str) -> MetadataEntry:
    return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _item(repo, *, extension="pdf", mime="application/pdf", chars=1200,
          status=IntakeItemStatus.AWAITING_REVIEW.value) -> UniversalObject:
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM,
        "paper.pdf",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry(KEY_INTAKE_STATUS, status),
                _entry(KEY_EXTENSION, extension),
                _entry(KEY_MIME_TYPE, mime),
                _entry(KEY_SIZE_BYTES, "2048"),
                _entry(
                    KEY_EXTRACTION,
                    json_encode({"status": "extracted", "format": "pdf", "char_count": chars}),
                ),
            )
        ),
    )
    repo.save(item)
    return item


def test_generation_maps_extension_and_facts():
    p = proposal_from_item(
        title="paper.pdf",
        document_type="pdf",
        extension="pdf",
        size_bytes=2048,
        mime_type="application/pdf",
        char_count=1200,
    )
    assert p.title == "paper.pdf"
    assert p.document_type == "pdf"
    assert "2048 bytes" in p.description
    assert "1200 characters" in p.description
    assert p.confidence == 1.0


def test_generation_unknown_type_low_confidence_without_text():
    p = proposal_from_item(
        title="weird.xyzzy",
        document_type="xyzzy",
        extension="xyzzy",
        size_bytes=100,
        mime_type=None,
        char_count=0,
    )
    assert p.document_type == "unknown"
    assert p.confidence == 0.6


def test_generate_persists_and_get_reads_back():
    repo = InMemoryRepo()
    item = _item(repo)
    engine = ProposalEngineService(repo)

    generated = engine.generate(str(item.id))
    assert generated.document_type == "pdf"
    assert generated.confidence == 1.0

    # Persisted as item metadata.
    stored = repo.get_by_id(item.id)
    assert stored is not None
    assert stored.metadata.get_value(KEY_PROPOSAL)

    # get() reads the same proposal back.
    fetched = engine.get(str(item.id))
    assert fetched == generated


def test_generate_is_idempotent_replace():
    repo = InMemoryRepo()
    item = _item(repo)
    engine = ProposalEngineService(repo)
    first = engine.generate(str(item.id))
    second = engine.generate(str(item.id))
    assert first == second


def test_missing_item_raises():
    engine = ProposalEngineService(InMemoryRepo())
    with pytest.raises(ObjectNotFoundError):
        engine.generate(str(ObjectId.generate(ObjectType.INTAKE_ITEM)))


def test_get_without_proposal_raises():
    repo = InMemoryRepo()
    item = _item(repo)
    with pytest.raises(ValidationError, match="no proposal"):
        ProposalEngineService(repo).get(str(item.id))
