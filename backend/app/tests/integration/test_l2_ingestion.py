"""L2 ingestion integration tests (ADR-028 / ADR-029).

Tests the orchestrator end-to-end against the L1 CDM store (SQLite):
source blob -> format -> engine -> NIR -> L1 CDM blocks + content projection.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.extraction import format_of
from app.application.services.cdm_service import CdmService
from app.application.services.extraction_orchestrator import ExtractionOrchestrator
from app.application.services.nir_mapper import NirMapper
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.source import MediaKind
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.extraction.registry import (
    build_container_expander,
    build_structured_parsers,
)
from app.infrastructure.persistence.cdm_store import SQLCdmStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import SQLAlchemyObjectRepository
from app.tests.unit.extraction_fixtures import (
    make_pdf_bytes,
    make_xlsx_bytes,
    make_zip_bytes,
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
    )


def test_ingest_pdf_writes_cdm_and_content(db):
    doc = _doc(db)
    res = _orch(db).ingest_blob(
        document=doc, blob=make_pdf_bytes("Hello L2"), file_name="a.pdf",
        extension="pdf", family="pdf", media_kind=MediaKind.from_extension("pdf"),
        version=1, blob_key="documents/x",
    )
    assert res.status == "extracted"
    assert res.elements >= 1
    cdm = CdmService(SQLCdmStore(db)).by_document("obj:document:1")
    assert len(cdm) >= 1


def test_ingest_xlsx_preserves_sheet_provenance(db):
    doc = _doc(db)
    data = make_xlsx_bytes([["Amount", 5000]])
    res = _orch(db).ingest_blob(
        document=doc, blob=data, file_name="b.xlsx", extension="xlsx",
        family="xlsx", media_kind=MediaKind.from_extension("xlsx"), version=1,
    )
    assert res.status == "extracted"
    assert res.sheets >= 1


def test_ingest_unsupported_is_honest(db):
    doc = _doc(db)
    res = _orch(db).ingest_blob(
        document=doc, blob=b"xyz", file_name="x.weird", extension="weird",
        family=format_of("weird"), media_kind=MediaKind.from_extension("weird"),
        version=1,
    )
    assert res.status == "unsupported"


def test_ingest_zip_members(db):
    doc = _doc(db)
    data = make_zip_bytes({"a.pdf": make_pdf_bytes("hello"), "note.txt": b"plain"})
    res = _orch(db).ingest_blob(
        document=doc, blob=data, file_name="pkg.zip", extension="zip",
        family="zip", media_kind=MediaKind.from_extension("zip"), version=1,
    )
    assert res.media_kind == "package"
    assert len(res.members) == 2
    assert all(m.ok for m in res.members)


def test_version_identity_and_supersession_cascade(db):
    """Source/version identity + supersession: a new version supersedes old."""
    from app.application.services.claim_service import ClaimService
    from app.application.services.version_cascade import VersionCascade
    from app.domain.value_objects.claim import ClaimStatus
    from app.infrastructure.persistence.claim_store import SQLClaimStore

    doc = _doc(db)
    # write v1 claims + CDM
    claims = ClaimService(SQLClaimStore(db))
    claims.propose(
        predicate_id="sanctioned_amount", raw_value=1000, source_text="v1",
        source_document_id="obj:document:1", source_version=1, spans=[], acl_scope=None,
    )
    orch = _orch(db)
    orch.ingest_blob(
        document=doc, blob=make_pdf_bytes("v1 content"), file_name="a.pdf",
        extension="pdf", family="pdf", media_kind=MediaKind.from_extension("pdf"),
        version=1,
    )
    cascade = VersionCascade(claims, SQLCdmStore(db))
    result = cascade.run(document_id="obj:document:1", old_version=1, new_version=2)
    assert result.claims_superseded == 1
    old_claims = claims._store.for_source_version("obj:document:1", 1)
    assert all(c.status is ClaimStatus.SUPERSEDED for c in old_claims)
