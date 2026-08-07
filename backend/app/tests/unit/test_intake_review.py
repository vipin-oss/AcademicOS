"""Unit tests for the Intake Review workflow (M9 — the Commit Engine gate).

Covers approve (commits through the engine, auto-proposes when the
pipeline produced no proposal), reject (terminal, never committable),
persisted review decisions, bulk approve/reject with per-item outcomes,
partial failures, and session/status guards.
"""
from __future__ import annotations

import pytest

from app.application.dtos.intake import (
    KEY_COMMITTED_DOCUMENT,
    KEY_EXTENSION,
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_MIME_TYPE,
    KEY_PROPOSAL,
    KEY_REVIEW_DECISION,
    KEY_SESSION_ID,
    KEY_SHA256,
    KEY_SIZE_BYTES,
    KEY_STAGED_KEY,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.use_cases.intake.review_item import (
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    ReviewItemUseCase,
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
from app.domain.value_objects.relationship import Relationship  # noqa: F401


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
        return out

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        obj = self._store.get(object_id)
        if obj is None:
            return []
        return obj.related_ids(kind)

    def find_inbound(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return [
            o.id
            for o in self._store.values()
            if any(r.target == object_id and (kind is None or r.kind == kind) for r in o.relationships)
        ]

    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        return self.find_by_type(object_type) if object_type is not None else self.list()

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        return len(
            self.find(
                object_type=object_type,
                status=status,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            )
        )


class InMemoryFileStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.blobs[key] = bytes(content)

    def read(self, key: str) -> bytes:
        if key not in self.blobs:
            raise FileNotFoundError(key)
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)

    def url(self, key: str) -> str:
        return f"http://test/{key}"


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _session(repo: InMemoryObjectRepository) -> UniversalObject:
    session = UniversalObject.create(
        ObjectType.INTAKE_SESSION,
        "M9 test session",
        created_by="u:1",
        status=ObjectStatus.ACTIVE,
    )
    session.set_metadata(
        _entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value), actor="u:1"
    )
    repo.save(session)
    return session


def _item(
    repo: InMemoryObjectRepository,
    session: UniversalObject,
    *,
    status: str = IntakeItemStatus.AWAITING_REVIEW.value,
    with_proposal: bool = True,
) -> UniversalObject:
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM,
        "report.pdf",
        created_by="u:1",
        status=ObjectStatus.ACTIVE,
    )
    extraction = json_encode({"status": "extracted", "char_count": 100})
    item.set_metadata(_entry(KEY_INTAKE_STATUS, status), actor="u:1")
    item.set_metadata(_entry(KEY_SESSION_ID, str(session.id)), actor="u:1")
    item.set_metadata(_entry(KEY_EXTENSION, "pdf"), actor="u:1")
    item.set_metadata(_entry(KEY_MIME_TYPE, "application/pdf"), actor="u:1")
    item.set_metadata(_entry(KEY_SIZE_BYTES, "2048"), actor="u:1")
    item.set_metadata(_entry(KEY_SHA256, "abc123"), actor="u:1")
    item.set_metadata(_entry(KEY_STAGED_KEY, "staging/session/report.pdf"), actor="u:1")
    item.set_metadata(_entry(KEY_EXTRACTION, extraction), actor="u:1")
    if with_proposal:
        item.set_metadata(
            _entry(
                KEY_PROPOSAL,
                json_encode(
                    {
                        "title": "report.pdf",
                        "document_type": "pdf",
                        "description": "seeded proposal",
                        "confidence": 1.0,
                    }
                ),
            ),
            actor="intake",
        )
    repo.save(item)
    return item


@pytest.fixture()
def world():
    repo = InMemoryObjectRepository()
    storage = InMemoryFileStorage()
    storage.save("staging/session/report.pdf", b"%PDF-1.7 fake bytes")
    session = _session(repo)
    return {"repo": repo, "storage": storage, "session": session}


def _review(world) -> ReviewItemUseCase:
    return ReviewItemUseCase(world["repo"], world["storage"])


def test_approve_commits_and_records_the_decision(world):
    repo = world["repo"]
    item = _item(repo, world["session"])

    out = _review(world).approve(str(item.id), actor="reviewer")

    assert out.document_id
    reloaded = repo.get_by_id(item.id)
    assert reloaded.metadata.get_value(KEY_INTAKE_STATUS) == IntakeItemStatus.COMMITTED.value
    assert reloaded.metadata.get_value(KEY_REVIEW_DECISION) == REVIEW_APPROVED
    assert reloaded.metadata.get_value(KEY_COMMITTED_DOCUMENT) == out.document_id
    # The document exists in the graph.
    assert repo.exists(ObjectId(out.document_id))


def test_approve_auto_generates_a_proposal_when_missing(world):
    repo = world["repo"]
    item = _item(repo, world["session"], with_proposal=False)

    out = _review(world).approve(str(item.id), actor="reviewer")

    assert out.document_id
    reloaded = repo.get_by_id(item.id)
    assert reloaded.metadata.get_value(KEY_INTAKE_STATUS) == IntakeItemStatus.COMMITTED.value
    # The proposal was generated from the item's facts.
    proposal = reloaded.metadata.get_value(KEY_PROPOSAL)
    assert proposal and "report.pdf" in proposal


def test_reject_is_terminal_and_records_the_decision(world):
    repo = world["repo"]
    item = _item(repo, world["session"])

    _review(world).reject(str(item.id), actor="reviewer")

    reloaded = repo.get_by_id(item.id)
    assert reloaded.metadata.get_value(KEY_INTAKE_STATUS) == IntakeItemStatus.REJECTED.value
    assert reloaded.metadata.get_value(KEY_REVIEW_DECISION) == REVIEW_REJECTED
    # A rejected item can never be committed.
    with pytest.raises(ValidationError):
        _review(world).approve(str(item.id), actor="reviewer")


def test_review_rejects_non_awaiting_items(world):
    repo = world["repo"]
    item = _item(repo, world["session"], status=IntakeItemStatus.ERROR.value)
    with pytest.raises(ValidationError, match="awaiting"):
        _review(world).approve(str(item.id), actor="reviewer")
    with pytest.raises(ValidationError, match="awaiting"):
        _review(world).reject(str(item.id), actor="reviewer")


def test_review_missing_item_raises_not_found(world):
    with pytest.raises(ObjectNotFoundError):
        _review(world).approve("obj:intake_item:missing", actor="reviewer")


def test_bulk_approve_commits_every_awaiting_item(world):
    repo = world["repo"]
    first = _item(repo, world["session"], with_proposal=False)
    second = _item(repo, world["session"], with_proposal=False)

    result = _review(world).bulk(str(world["session"].id), REVIEW_APPROVED, actor="reviewer")

    assert result.succeeded == 2
    assert {i.item_id for i in result.items} == {str(first.id), str(second.id)}
    assert all(i.document_id for i in result.items)
    assert all(
        repo.get_by_id(ObjectId(i.item_id)).metadata.get_value(KEY_INTAKE_STATUS)
        == IntakeItemStatus.COMMITTED.value
        for i in result.items
    )


def test_bulk_reject_rejects_every_awaiting_item(world):
    repo = world["repo"]
    _item(repo, world["session"])
    _item(repo, world["session"])

    result = _review(world).bulk(str(world["session"].id), REVIEW_REJECTED, actor="reviewer")

    assert result.succeeded == 2
    for i in result.items:
        assert repo.get_by_id(ObjectId(i.item_id)).metadata.get_value(KEY_INTAKE_STATUS) \
            == IntakeItemStatus.REJECTED.value


def test_bulk_honours_an_explicit_subset(world):
    repo = world["repo"]
    target = _item(repo, world["session"])
    other = _item(repo, world["session"])

    result = _review(world).bulk(
        str(world["session"].id), REVIEW_APPROVED, actor="reviewer", item_ids=[str(target.id)]
    )

    assert [i.item_id for i in result.items] == [str(target.id)]
    assert repo.get_by_id(other.id).metadata.get_value(KEY_INTAKE_STATUS) \
        == IntakeItemStatus.AWAITING_REVIEW.value


def test_bulk_reports_partial_failures_per_item(world):
    repo = world["repo"]
    good = _item(repo, world["session"])
    already = _item(repo, world["session"], status=IntakeItemStatus.ERROR.value)

    result = _review(world).bulk(
        str(world["session"].id), REVIEW_APPROVED, actor="reviewer",
        item_ids=[str(good.id), str(already.id)],
    )

    by_id = {i.item_id: i for i in result.items}
    assert by_id[str(good.id)].document_id
    assert by_id[str(already.id)].error
    assert result.succeeded == 1


def test_bulk_rejects_unknown_decision(world):
    with pytest.raises(ValidationError, match="decision"):
        _review(world).bulk(str(world["session"].id), "maybe", actor="reviewer")


def test_bulk_requires_a_completed_session(world):
    repo = world["repo"]
    session = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "pending session", created_by="u:1",
        status=ObjectStatus.ACTIVE,
    )
    session.set_metadata(_entry(KEY_INTAKE_STATUS, IntakeSessionStatus.RUNNING.value), actor="u:1")
    repo.save(session)
    _item(repo, session)

    with pytest.raises(ValidationError, match="completed"):
        _review(world).bulk(str(session.id), REVIEW_APPROVED, actor="reviewer")


def test_bulk_reports_already_committed_per_item(world):
    repo = world["repo"]
    first = _item(repo, world["session"])
    second = _item(repo, world["session"])
    # Commit the first item directly, then bulk-approve the session: the
    # already-committed item must be reported, not crash the request.
    _review(world).approve(str(first.id), actor="reviewer")

    result = _review(world).bulk(
        str(world["session"].id), REVIEW_APPROVED, actor="reviewer",
        item_ids=[str(first.id), str(second.id)],
    )

    by_id = {i.item_id: i for i in result.items}
    assert by_id[str(first.id)].error  # already committed -> per-item error
    assert by_id[str(second.id)].document_id  # the remaining awaiting item commits
    assert result.succeeded == 1
