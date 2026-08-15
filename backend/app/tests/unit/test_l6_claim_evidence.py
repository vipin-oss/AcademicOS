"""L6 claim-evidence service tests (ADR-039, §13.6)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_evidence import ClaimEvidenceService
from app.application.services.claim_service import ClaimService
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.enums import ObjectStatus, ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


class _FakePerm:
    def __init__(self, allow_read: bool = True):
        self._allow_read = allow_read

    def can(self, *, principal, scope, action):
        return action is PermissionAction.READ and self._allow_read


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
def repo(db):
    r = SQLAlchemyObjectRepository(db)
    r.save(UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l6-1"),
    ))
    return r


def _user():
    return UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l6-1"),
    )


def _span():
    return Span(kind=SpanKind.PAGE, source_id="obj:document:1", page=2)


def _propose_confirm(db, *, pred="sanctioned_amount", value=1000, scope=None):
    claims = ClaimService(SQLClaimStore(db))
    claim = claims.propose(
        predicate_id=pred, raw_value=value, source_text="v1",
        source_document_id="obj:document:1", source_version=1,
        spans=[_span()], acl_scope=scope, fact_confidence=0.95,
    )
    claims.confirm(claim.claim_id, reviewer="u:1", assert_human=True)
    return claim


def test_only_authoritative_claims_citable(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    # CONFIRMED -> citable
    _propose_confirm(db, scope='{"owner":"obj:user:l6-1"}')
    # PROPOSED (not confirmed) -> not citable
    ClaimService(SQLClaimStore(db)).propose(
        predicate_id="issue_date", raw_value="2026-01-01", source_text="d",
        source_document_id="obj:document:1", source_version=1, spans=[_span()],
        acl_scope='{"owner":"obj:user:l6-1"}',
    )
    cites = svc.citable_claims(user=_user())
    assert len(cites) == 1
    assert cites[0].predicate_id == "sanctioned_amount"
    assert cites[0].authoritative is True


def test_acl_denied_claim_excluded(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm(allow_read=False))
    _propose_confirm(db, scope='{"owner":"obj:user:other"}')
    cites = svc.citable_claims(user=_user())
    assert cites == []  # no leakage


def test_source_span_preserved(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    _propose_confirm(db, scope='{"owner":"obj:user:l6-1"}')
    cites = svc.citable_claims(user=_user())
    assert cites[0].span is not None
    assert cites[0].span.get("page") == 2


def test_confidence_tiers_present(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    _propose_confirm(db, scope='{"owner":"obj:user:l6-1"}', value=1000)
    cites = svc.citable_claims(user=_user())
    conf = cites[0].confidence
    assert conf.fact_tier in ("high", "medium", "low")
    assert conf.fact_confidence == 0.95


def test_deterministic_order_and_dedup(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    scope = '{"owner":"obj:user:l6-1"}'
    _propose_confirm(db, pred="sanctioned_amount", scope=scope)
    _propose_confirm(db, pred="issue_date", scope=scope)
    a = svc.citable_claims(user=_user())
    b = svc.citable_claims(user=_user())
    assert [c.claim_id for c in a] == [c.claim_id for c in b]
    assert len({c.claim_id for c in a}) == len(a)  # no duplicates


def test_rejected_or_superseded_not_citable(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    claim = _propose_confirm(db, scope='{"owner":"obj:user:l6-1"}')
    # supersede it
    ClaimService(SQLClaimStore(db)).supersede_claim(claim.claim_id, "claim:new")
    cites = svc.citable_claims(user=_user())
    assert all(c.claim_id != claim.claim_id for c in cites)


def test_evidence_set_reuses_object_citations_and_is_bounded(db):
    from app.application.dtos.assistant import AssistantCitation
    from app.application.dtos.evidence import FactCitation
    from app.application.services.claim_evidence import assemble_evidence_set

    object_citations = [
        AssistantCitation(
            number=1, object_id="obj:doc:1", object_type="document",
            title="A", sources=(), version=1, score=0.9,
        )
    ]
    fact_citations = [
        FactCitation(
            number=1, claim_id="claim:1", predicate_id="sanctioned_amount",
            source_document_id="obj:doc:1", source_version=1, span=None,
            value={"amount": 1000},
        ),
        FactCitation(
            number=2, claim_id="claim:2", predicate_id="issue_date",
            source_document_id="obj:doc:1", source_version=1,
        ),
    ]
    ev = assemble_evidence_set(object_citations, fact_citations, limit=2)
    assert len(ev) == 2  # bounded
    # object citations preserved first, then fact citations
    assert ev.object_citations[0].object_id == "obj:doc:1"
    assert [f.claim_id for f in ev.fact_citations] == ["claim:1"]
    # non-authoritative facts are never admitted
    assert assemble_evidence_set(
        object_citations, fact_citations, limit=50
    ).fact_citations == tuple(fact_citations)
