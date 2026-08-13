"""L1 format-agnostic SOURCE contract tests (ADR-023)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.source_service import read_source_contract, register_source
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.source import MediaKind, SourceContract
from app.infrastructure.db.models.object_model import Base
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


def _doc(db) -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "Sanction letter", created_by="u:1",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:document:1"),
    )
    SQLAlchemyObjectRepository(db).save(obj)
    return obj


def test_media_kind_from_extension():
    assert MediaKind.from_extension("pdf") is MediaKind.TEXT_LAYOUT
    assert MediaKind.from_extension("XLSX") is MediaKind.SPREADSHEET
    assert MediaKind.from_extension("png") is MediaKind.RASTER_IMAGE
    assert MediaKind.from_extension("pptx") is MediaKind.SLIDES
    assert MediaKind.from_extension("zip") is MediaKind.PACKAGE
    assert MediaKind.from_extension("weird") is MediaKind.UNKNOWN


def _save(db, doc) -> None:
    SQLAlchemyObjectRepository(db).save(doc)


def test_register_and_read_roundtrip(db):
    doc = _doc(db)
    contract = SourceContract(
        source_id=str(doc.id),
        media_kind=MediaKind.RASTER_IMAGE,
        blob_key="blobs/scanned_letter.png",
        version=1,
    )
    register_source(doc, contract)
    _save(db, doc)  # the caller persists the contract metadata
    doc = SQLAlchemyObjectRepository(db).get_by_id(doc.id)
    assert doc is not None
    read = read_source_contract(doc)
    assert read.media_kind is MediaKind.RASTER_IMAGE
    assert read.blob_key == "blobs/scanned_letter.png"
    assert read.source_id == "obj:document:1"


def test_container_provenance(db):
    doc = _doc(db)
    contract = SourceContract(
        source_id=str(doc.id),
        media_kind=MediaKind.PLAIN_TEXT,
        blob_key="blobs/member.txt",
        container_source_id="obj:document:0",
        container_path="bundle/inner.txt",
        version=1,
    )
    assert contract.is_package_member is True
    register_source(doc, contract)
    _save(db, doc)
    doc = SQLAlchemyObjectRepository(db).get_by_id(doc.id)
    read = read_source_contract(doc)
    assert read.container_source_id == "obj:document:0"
    assert read.container_path == "bundle/inner.txt"


def test_engine_stamp(db):
    doc = _doc(db)
    base = SourceContract(
        source_id=str(doc.id), media_kind=MediaKind.TEXT_LAYOUT,
        blob_key="blobs/x.pdf", version=1,
    )
    stamped = base.with_evidence(engine="pypdf", engine_version=2)
    assert stamped.engine == "pypdf"
    assert stamped.engine_version == 2
    register_source(doc, stamped)
    _save(db, doc)
    doc = SQLAlchemyObjectRepository(db).get_by_id(doc.id)
    read = read_source_contract(doc)
    assert read.engine == "pypdf"
    assert read.engine_version == 2
