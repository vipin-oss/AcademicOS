"""L1 ACL propagation tests (ADR-009 / ADR-026)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.object import ACL_READERS
from app.infrastructure.persistence.acl_scope_propagator import AclScopePropagator
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _doc(db, reader: str) -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "Letter", created_by="u:1",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:document:1"),
    )
    obj.set_metadata(
        MetadataEntry(ACL_READERS, json.dumps([reader]),
                      MetadataLayer.L1_SYSTEM, Provenance.ASSERTED),
        actor="u:1",
    )
    SQLAlchemyObjectRepository(db).save(obj)
    return obj


def test_propagates_to_all_derived_rows(db):
    doc = _doc(db, "u:2")
    # seed derived rows (as an applier would)
    db.add(SearchDocumentModel(
        object_id=str(doc.id), object_type="document", title="Letter",
        metadata_text="", version=1, acl_scope=None,
    ))
    db.add(DocumentContentModel(
        object_id=str(doc.id), version=1, content_text="x", source_item_id="i1",
        created_at="now", acl_scope=None,
    ))
    db.add(DocumentChunkModel(
        document_id=str(doc.id), chunk_index=0, content="x", char_start=0,
        char_end=1, token_count=1, content_hash="h", version=1, created_at="now",
        acl_scope=None,
    ))
    db.flush()

    AclScopePropagator(db).propagate(doc)
    db.flush()

    # search_documents
    sd = db.query(SearchDocumentModel).filter_by(object_id=str(doc.id)).first()
    assert sd is not None and sd.acl_scope is not None
    parsed = json.loads(sd.acl_scope)
    assert "u:2" in parsed["readers"]
    # contents + chunks
    content = db.query(DocumentContentModel).filter_by(object_id=str(doc.id)).first()
    assert content.acl_scope is not None
    chunk = db.query(DocumentChunkModel).filter_by(document_id=str(doc.id)).first()
    assert chunk.acl_scope is not None
