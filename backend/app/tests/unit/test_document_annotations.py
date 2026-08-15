"""Unit tests for document annotations (Sprint M10 — viewer framework).

Covers the record invariants (identity, type domain, 1-based page,
non-empty payload), the store round-trips (page/creation ordering,
update, delete), and the service guards (document-exists, extracted-text
resolution through the linked intake item).
"""
from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.annotation import (
    ANNOTATION_BOOKMARK,
    ANNOTATION_HIGHLIGHT,
    ANNOTATION_NOTE,
    DocumentAnnotation,
    new_annotation,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.annotation_model import DocumentAnnotationModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def world(db):
    repo = SQLAlchemyObjectRepository(db)
    store = SQLAnnotationStore(db)
    service = DocumentAnnotationService(repo, store)
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "paper.pdf", created_by="u:1", status=ObjectStatus.ACTIVE
    )
    doc.pop_domain_events()
    repo.save(doc)
    return {"repo": repo, "store": store, "service": service, "doc": doc}


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


# --------------------------------------------------------------- invariants
def test_annotation_invariants_are_enforced():
    with pytest.raises(ValueError, match="type"):
        new_annotation(
            document_id="d", annotation_type="sticky", page=1,
            payload={"x": 1}, created_by="u",
        )
    with pytest.raises(ValueError, match="page"):
        new_annotation(
            document_id="d", annotation_type=ANNOTATION_NOTE, page=0,
            payload={"text": "x"}, created_by="u",
        )
    with pytest.raises(ValueError, match="payload"):
        new_annotation(
            document_id="d", annotation_type=ANNOTATION_NOTE, page=1,
            payload={}, created_by="u",
        )
    with pytest.raises(ValueError, match="identity"):
        new_annotation(
            document_id="", annotation_type=ANNOTATION_NOTE, page=1,
            payload={"text": "x"}, created_by="u",
        )


# ------------------------------------------------------------------- store
def test_store_round_trip_and_ordering(db, world):
    store = world["store"]
    doc_id = str(world["doc"].id)
    first = store.add(
        new_annotation(
            document_id=doc_id, annotation_type=ANNOTATION_NOTE, page=2,
            payload={"text": "second page note"}, created_by="u",
        )
    )
    second = store.add(
        new_annotation(
            document_id=doc_id, annotation_type=ANNOTATION_BOOKMARK, page=1,
            payload={"label": "start"}, created_by="u",
        )
    )
    ordered = store.by_document(doc_id)
    assert [a.page for a in ordered] == [1, 2]
    assert ordered[0].annotation_id == second.annotation_id
    assert store.get(first.annotation_id) == first

    # update mutates page/payload and stamps updated_at.
    updated = store.update(
        DocumentAnnotation(
            annotation_id=first.annotation_id,
            document_id=doc_id,
            annotation_type=ANNOTATION_NOTE,
            page=3,
            payload={"text": "moved"},
            created_by="u",
            created_at=first.created_at,
            updated_at="2026-08-07T00:00:00+00:00",
        )
    )
    assert updated.page == 3
    assert store.get(first.annotation_id).payload == {"text": "moved"}

    assert store.delete(first.annotation_id) is True
    assert store.get(first.annotation_id) is None
    assert store.delete(first.annotation_id) is False


# ----------------------------------------------------------------- service
def test_service_create_and_list(world):
    service, doc = world["service"], world["doc"]
    created = service.create(
        document_id=str(doc.id),
        annotation_type=ANNOTATION_HIGHLIGHT,
        page=1,
        payload={"rects": [{"x0": 0, "y0": 0, "x1": 10, "y1": 10}], "text": "wave"},
        created_by="u",
    )
    items = service.list(str(doc.id))
    assert len(items) == 1
    assert items[0].annotation_id == created.annotation_id

    service.delete(created.annotation_id)
    assert service.list(str(doc.id)) == []


def test_service_requires_an_existing_document(world):
    service = world["service"]
    with pytest.raises(ObjectNotFoundError):
        service.create(
            document_id="obj:document:missing",
            annotation_type=ANNOTATION_NOTE,
            page=1,
            payload={"text": "x"},
            created_by="u",
        )
    with pytest.raises(ObjectNotFoundError):
        service.list("obj:document:missing")


def test_service_update_and_delete_missing(world):
    service = world["service"]
    with pytest.raises(ObjectNotFoundError):
        service.update("no-such-annotation", page=2)
    with pytest.raises(ObjectNotFoundError):
        service.delete("no-such-annotation")


def test_extracted_text_resolves_the_linked_intake_item(world):
    repo, service = world["repo"], world["service"]
    doc = world["doc"]
    # A completed intake session + extracted item, linked via BELONGS_TO.
    session_obj = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "session", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=__import__("app.domain.value_objects.metadata", fromlist=["Metadata"]).Metadata(
            entries=(
                _entry("intake.status", "completed"),
            )
        ),
    )
    repo.save(session_obj)
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM, "paper.pdf", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=__import__("app.domain.value_objects.metadata", fromlist=["Metadata"]).Metadata(
            entries=(
                _entry("intake.status", "committed"),
                _entry("intake.session_id", str(session_obj.id)),
                _entry(
                    "intake.extraction",
                    '{"status": "extracted", "text_key": "extract/paper.txt"}',
                ),
            )
        ),
    )
    repo.save(item)
    doc.add_relationship(item.id, RelationshipKind.BELONGS_TO, actor="system")
    repo.save(doc)

    class _Storage:
        def exists(self, key):
            return key == "extract/paper.txt"

        def read(self, key):
            return b"Propagation of waves in piezothermoelastic media"

    result = service.extracted_text(str(doc.id), _Storage())
    assert result is not None
    assert "piezothermoelastic" in result["text"]
    assert result["item_id"] == str(item.id)
    assert result["session_id"] == str(session_obj.id)


def test_extracted_text_none_without_link(world):
    service = world["service"]
    assert service.extracted_text(str(world["doc"].id), None) is None
