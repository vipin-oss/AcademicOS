"""Unit tests for the Intake Commit Engine (Sprint-3 M1.1 + M1.2)."""
from __future__ import annotations

import pytest

from app.application.commands.commit_intake_item import CommitIntakeItemCommand
from app.application.dtos.intake import (
    KEY_EXTENSION,
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_MIME_TYPE,
    KEY_SESSION_ID,
    KEY_SHA256,
    KEY_SIZE_BYTES,
    KEY_STAGED_KEY,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.intake.commit_engine import CommitEngineService
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.use_cases.intake.commit_item import CommitItemUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    """Test double implementing the full abstract port."""

    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(
        self, key: str, value: str | None = None
    ) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
        return out

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


class InMemoryFileStorage(FileStorage):
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


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _extracted_descriptor() -> str:
    return json_encode(
        {
            "status": "extracted",
            "format": "pdf",
            "char_count": 1200,
            "engine": "pypdf",
        }
    )


def _completed_session(repo: InMemoryObjectRepository) -> UniversalObject:
    session = UniversalObject.create(
        ObjectType.INTAKE_SESSION,
        "session",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value),
            )
        ),
    )
    session_id = str(session.id)
    _ = session_id
    repo.save(session)
    return session


def _awaiting_item(
    repo: InMemoryObjectRepository,
    session: UniversalObject,
    *,
    status: str = IntakeItemStatus.AWAITING_REVIEW.value,
    with_blob: bool = True,
    with_hash: bool = True,
    extraction: str | None = None,
    extension: str = "pdf",
) -> UniversalObject:
    if extraction is None:
        extraction = _extracted_descriptor()
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM,
        "report.pdf",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(
                _entry(KEY_INTAKE_STATUS, status),
                _entry(KEY_SESSION_ID, str(session.id)),
                _entry(KEY_EXTENSION, extension),
                _entry(KEY_MIME_TYPE, "application/pdf"),
                _entry(KEY_SIZE_BYTES, str(2048)),
                _entry(KEY_SHA256, "abc123" if with_hash else ""),
                _entry(KEY_STAGED_KEY, "staging/session/report.pdf"),
                _entry(KEY_EXTRACTION, extraction),
            )
        ),
    )
    repo.save(item)
    # A reviewed proposal (the Sprint-3 M2 commit gate).
    from app.application.dtos.intake import KEY_PROPOSAL

    item.set_metadata(
        MetadataEntry(
            KEY_PROPOSAL,
            json_encode(
                {
                    "title": item.title,
                    "document_type": extension,
                    "description": "seeded proposal",
                    "confidence": 1.0,
                }
            ),
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
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
    return {"repo": repo, "storage": storage}


def _engine(world) -> CommitEngineService:
    return CommitEngineService(world["repo"], world["storage"])


def test_commit_happy_path_creates_document_and_marks_item(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)

    out = _engine(world).commit_item(str(item.id), actor="faculty:1")

    assert out.item_id == str(item.id)
    assert out.document_id.startswith("obj:document:")
    assert out.document_title == "report.pdf"

    # The item is terminal-committed with a pointer to the document.
    committed = world["repo"].get_by_id(item.id)
    assert committed is not None
    assert committed.metadata.get_value(KEY_INTAKE_STATUS) == IntakeItemStatus.COMMITTED.value
    assert committed.metadata.get_value("intake.committed_document") == out.document_id

    # Exactly one document was created; it is ACTIVE and typed by extension.
    documents = [o for o in world["repo"].list() if o.object_type is ObjectType.DOCUMENT]
    assert len(documents) == 1
    doc = documents[0]
    assert doc.status is ObjectStatus.ACTIVE
    assert doc.metadata.get_value("document_type") == "pdf"
    # The BELONGS_TO edge (document -> item) came from CreateDocumentUseCase.
    assert any(r.kind is RelationshipKind.BELONGS_TO and r.target == item.id for r in doc.relationships)
    # Inbound traversal on the item finds the document.
    assert world["repo"].find_inbound(item.id) == [doc.id]


def test_commit_is_idempotent(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)
    engine = _engine(world)

    first = engine.commit_item(str(item.id), actor="faculty:1")
    with pytest.raises(ObjectAlreadyExistsError, match=first.document_id):
        engine.commit_item(str(item.id), actor="faculty:1")

    # Still exactly one document — never a duplicate write.
    documents = [o for o in world["repo"].list() if o.object_type is ObjectType.DOCUMENT]
    assert len(documents) == 1


def test_commit_rejects_non_awaiting_status(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session, status=IntakeItemStatus.STAGED.value)
    with pytest.raises(ValidationError, match="status"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_rejects_unstaged_item(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session, with_hash=False)
    with pytest.raises(ValidationError, match="staged"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_rejects_unextracted_item(world):
    session = _completed_session(world["repo"])
    descriptor = json_encode({"status": "unsupported", "format": "weird"})
    item = _awaiting_item(world["repo"], session, extraction=descriptor)
    with pytest.raises(ValidationError, match="extracted"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_rejects_uncompleted_session(world):
    session = UniversalObject.create(
        ObjectType.INTAKE_SESSION,
        "session",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=(_entry(KEY_INTAKE_STATUS, IntakeSessionStatus.RUNNING.value),)
        ),
    )
    world["repo"].save(session)
    item = _awaiting_item(world["repo"], session)
    with pytest.raises(ValidationError, match="completed"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_rejects_missing_staged_blob(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)
    world["storage"].delete("staging/session/report.pdf")
    with pytest.raises(ValidationError, match="missing"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_missing_item_raises_not_found(world):
    with pytest.raises(ObjectNotFoundError):
        _engine(world).commit_item(str(ObjectId.generate(ObjectType.INTAKE_ITEM)), actor="f:1")


def test_commit_maps_unknown_extension_to_unknown_type(world):
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session, extension="xyzzy")
    out = _engine(world).commit_item(str(item.id), actor="faculty:1")
    doc = world["repo"].get_by_id(ObjectId(out.document_id))
    assert doc is not None
    assert doc.metadata.get_value("document_type") == "unknown"


def test_engine_wires_and_delegates_to_the_use_case(world):
    """CommitEngineService is the single entry point; the use case is the
    logic unit. Both paths agree (a second commit conflicts identically)."""
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)
    engine = CommitEngineService(world["repo"], world["storage"])
    out = engine.commit_item(str(item.id), actor="f:1")

    direct = CommitItemUseCase(
        world["repo"],
        world["storage"],
        CreateDocumentUseCase(world["repo"], world["storage"]),
    )
    with pytest.raises(ObjectAlreadyExistsError):
        direct.execute(CommitIntakeItemCommand(item_id=str(item.id), actor="f:1"))
    assert out.document_id

def test_commit_requires_reviewed_proposal(world):
    """The proposal gate: without a reviewed proposal the commit is 422."""
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)
    # Drop the proposal the seed helper added.
    from app.application.dtos.intake import KEY_PROPOSAL

    item.set_metadata(
        MetadataEntry(KEY_PROPOSAL, "", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="intake",
    )
    world["repo"].save(item)

    with pytest.raises(ValidationError, match="proposal"):
        _engine(world).commit_item(str(item.id), actor="faculty:1")


def test_commit_uses_reviewed_title_and_type(world):
    """The reviewed proposal drives the created document's title/type."""
    session = _completed_session(world["repo"])
    item = _awaiting_item(world["repo"], session)
    from app.application.dtos.intake import KEY_PROPOSAL

    item.set_metadata(
        MetadataEntry(
            KEY_PROPOSAL,
            json_encode(
                {
                    "title": "Reviewed Title",
                    "document_type": "txt",
                    "description": "human reviewed",
                    "confidence": 1.0,
                }
            ),
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="faculty:1",
    )
    world["repo"].save(item)

    out = _engine(world).commit_item(str(item.id), actor="faculty:1")
    assert out.document_title == "Reviewed Title"
    doc = world["repo"].get_by_id(ObjectId(out.document_id))
    assert doc is not None
    assert doc.title == "Reviewed Title"
    assert doc.metadata.get_value("document_type") == "txt"
