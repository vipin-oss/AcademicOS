"""L1 file-version -> claim/CDM supersession cascade tests (ADR-021 / ADR-027)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.cdm_service import CdmService
from app.application.services.version_cascade import VersionCascade
from app.domain.value_objects.cdm import CdmBlockType
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.cdm_store import SQLCdmStore


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


@pytest.fixture()
def cascade(db):
    claims = ClaimService(SQLClaimStore(db))
    cdm = CdmService(SQLCdmStore(db))
    return VersionCascade(claims, SQLCdmStore(db))


def test_cascade_supersedes_claims_and_marks_cdm(db, cascade):
    # v1 claims
    claims = ClaimService(SQLClaimStore(db))
    claims.propose(
        predicate_id="sanctioned_amount", raw_value=1000,
        source_text="v1", source_document_id="obj:document:1", source_version=1,
        spans=[], acl_scope=None,
    )
    # v1 cdm blocks
    CdmService(SQLCdmStore(db)).replace_blocks(
        document_id="obj:document:1", version=1,
        blocks=[CdmService.make_block(CdmBlockType.HEADING, 0)],
    )
    result = cascade.run(document_id="obj:document:1", old_version=1, new_version=2)
    assert result.claims_superseded == 1
    assert result.cdm_blocks_superseded == 1

    old_claims = claims._store.for_source_version("obj:document:1", 1)
    assert all(c.status is ClaimStatus.SUPERSEDED for c in old_claims)
    # new placeholder proposed on v2 (re-extraction by an L2 engine)
    new_claims = claims._store.for_source_version("obj:document:1", 2)
    assert any(c.status is ClaimStatus.PROPOSED for c in new_claims)

    # cdm old blocks marked superseded, not deleted
    cdm = CdmService(SQLCdmStore(db))
    old_blocks = cdm.by_document("obj:document:1", version=1)
    assert old_blocks[0].payload.get("superseded") is True
    assert old_blocks[0].payload.get("superseded_by_version") == 2
