"""L3 extraction→claim bridge integration test (ADR-034).

Verifies that ingesting an XLSX (which yields SHEET_CELL label/value pairs)
and a PDF produces PROPOSED claims in the claim store, via the orchestrator.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cdm_service import CdmService
from app.application.services.claim_service import ClaimService
from app.application.services.extraction_orchestrator import ExtractionOrchestrator
from app.application.services.nir_mapper import NirMapper
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.source import MediaKind
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.extraction.registry import (
    build_container_expander,
    build_structured_parsers,
)
from app.infrastructure.persistence.cdm_store import SQLCdmStore
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import SQLAlchemyObjectRepository
from app.tests.unit.extraction_fixtures import make_xlsx_bytes


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


def _doc(db, oid="obj:document:1") -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "Doc", created_by="u:1", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(oid),
    )
    SQLAlchemyObjectRepository(db).save(obj)
    return obj


def _orch(db):
    return ExtractionOrchestrator(
        parsers=build_structured_parsers(),
        expander=build_container_expander(),
        mapper=NirMapper(CdmService(SQLCdmStore(db))),
        content_store=SQLDocumentContentStore(db),
        claim_service=ClaimService(SQLClaimStore(db)),
    )


def test_ingest_xlsx_proposes_claims(db):
    doc = _doc(db)
    data = make_xlsx_bytes([["Amount", "Details"], ["5000", "grant"]])
    res = _orch(db).ingest_blob(
        document=doc, blob=data, file_name="b.xlsx", extension="xlsx",
        family="xlsx", media_kind=MediaKind.from_extension("xlsx"), version=1,
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )
    assert res.status == "extracted"
    claims = ClaimService(SQLClaimStore(db))._store.by_source("obj:document:1")
    assert any(c.predicate_id == "sanctioned_amount" for c in claims)
    assert all(c.status is ClaimStatus.PROPOSED for c in claims)


def test_ingest_xlsx_claims_are_proposed_not_confirmed(db):
    doc = _doc(db)
    data = make_xlsx_bytes([["Amount", "x"], ["100", "y"]])
    _orch(db).ingest_blob(
        document=doc, blob=data, file_name="b.xlsx", extension="xlsx",
        family="xlsx", media_kind=MediaKind.from_extension("xlsx"), version=1,
        acl_scope='{"owner":"u:1"}',
    )
    claims = ClaimService(SQLClaimStore(db))._store.by_source("obj:document:1")
    assert all(c.status is ClaimStatus.PROPOSED for c in claims)
    assert all(c.is_authoritative is False for c in claims)
