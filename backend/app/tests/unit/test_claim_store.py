"""L1 claim store + lifecycle tests (ADR-002 / ADR-019 / ADR-006 / ADR-021)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.domain.value_objects.claim import ClaimStatus, confidence_tier
from app.domain.value_objects.enums import Provenance
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore


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
def service(db):
    return ClaimService(SQLClaimStore(db))


def _span(**kw) -> Span:
    base = dict(kind=SpanKind.PAGE, source_id="obj:document:1", page=3)
    base.update(kw)
    return Span(**base)


def test_propose_valid_predicate_binds_to_catalogue(service):
    claim = service.propose(
        predicate_id="sanctioned_amount",
        raw_value="₹50,00,000",
        source_text="Sanctioned amount is fifty lakh rupees.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[_span()],
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
        fact_confidence=0.95,
    )
    assert claim.status is ClaimStatus.PROPOSED
    assert claim.value_schema == "money"
    assert claim.value["amount"] == 5000000.0
    assert not claim.is_authoritative  # PROPOSED is not canonical


def test_unknown_predicate_is_stored_as_raw_not_dropped(service):
    claim = service.propose(
        predicate_id="no_such_predicate",
        raw_value="anything",
        source_text="Some extraction text.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
    )
    assert claim.value_schema == "raw"
    assert claim.value["kind"] == "raw"
    assert claim.value["reason"] == "unknown_predicate"


def test_ocr_derived_fact_confidence_is_capped_at_medium(service):
    claim = service.propose(
        predicate_id="sanctioned_amount",
        raw_value=1000,
        source_text="One thousand.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
        fact_confidence=0.98,
        ocr_derived=True,
    )
    assert claim.fact_confidence <= 0.7


def test_confirm_persists_provenance_asserted(service):
    claim = service.propose(
        predicate_id="principal_investigator",
        raw_value="Dr. Nair",
        source_text="PI: Dr. Nair.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
    )
    service.confirm(claim.claim_id, reviewer="u:1", assert_human=True)
    stored = service._store.get(claim.claim_id)
    assert stored is not None
    reloaded, _ = stored
    assert reloaded.status is ClaimStatus.CONFIRMED
    assert reloaded.provenance is Provenance.ASSERTED


def test_spans_roundtrip(service):
    span = _span(kind=SpanKind.TABLE_CELL, table_id="t1", row_idx=2, col_idx=0)
    claim = service.propose(
        predicate_id="sanctioned_amount",
        raw_value=5000,
        source_text="Cell value.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[span],
        acl_scope=None,
    )
    stored = service._store.get(claim.claim_id)
    _, spans = stored
    assert len(spans) == 1
    assert spans[0].kind is SpanKind.TABLE_CELL
    assert spans[0].table_id == "t1"


def test_supersede_without_delete(service):
    old = service.propose(
        predicate_id="sanctioned_amount",
        raw_value=1000,
        source_text="Old amount.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
    )
    new = service.propose(
        predicate_id="sanctioned_amount",
        raw_value=2000,
        source_text="New amount.",
        source_document_id="obj:document:1",
        source_version=2,
        spans=[],
        acl_scope=None,
    )
    superseded = service.supersede_claim(old.claim_id, new.claim_id)
    assert superseded.status is ClaimStatus.SUPERSEDED
    stored = service._store.get(old.claim_id)
    assert stored is not None and stored[0].status is ClaimStatus.SUPERSEDED


def test_supersede_for_source_version(service):
    service.propose(
        predicate_id="sanctioned_amount",
        raw_value=1000,
        source_text="v1",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
    )
    n = service.supersede_for_source_version("obj:document:1", 1, 2)
    assert n == 1
    # old claim superseded, nothing deleted
    old = service._store.for_source_version("obj:document:1", 1)
    assert len(old) == 1 and old[0].status is ClaimStatus.SUPERSEDED
    # a placeholder proposed on v2
    new = service._store.for_source_version("obj:document:1", 2)
    assert any(c.status is ClaimStatus.PROPOSED for c in new)


def test_rejected_cannot_be_promoted(service):
    claim = service.propose(
        predicate_id="issue_date",
        raw_value="2026-01-01",
        source_text="Date.",
        source_document_id="obj:document:1",
        source_version=1,
        spans=[],
        acl_scope=None,
    )
    service.reject(claim.claim_id, reviewer="u:1")
    with pytest.raises(ValueError):
        service.confirm(claim.claim_id, reviewer="u:1")


def test_confidence_tier():
    assert confidence_tier(0.95) == "high"
    assert confidence_tier(0.65) == "medium"
    assert confidence_tier(0.3) == "low"
