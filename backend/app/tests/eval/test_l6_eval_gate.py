"""L6 evaluation gate (ADR-040).

Verifies real L6 evidence/citation behavior against the frozen §13.6 laws using
the L0 capability-evaluation framework's conventions. No L0 framework
modification.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_evidence import ClaimEvidenceService
from app.application.services.claim_service import ClaimService
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore


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


def _user():
    return UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l6e-1"),
    )


def _seed(db, *, pred="sanctioned_amount", value=1000, scope='{"owner":"obj:user:l6e-1"}', confirm=True):
    claims = ClaimService(SQLClaimStore(db))
    claim = claims.propose(
        predicate_id=pred, raw_value=value, source_text="v1",
        source_document_id="obj:document:1", source_version=1,
        spans=[Span(kind=SpanKind.PAGE, source_id="obj:document:1", page=2)],
        acl_scope=scope, fact_confidence=0.95,
    )
    if confirm:
        claims.confirm(claim.claim_id, reviewer="u:1", assert_human=True)
    return claim


def test_gate_fact_citation_eligibility(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    _seed(db)  # CONFIRMED
    cites = svc.citable_claims(user=_user())
    assert len(cites) == 1
    assert cites[0].authoritative is True


def test_gate_acl_isolation(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm(allow_read=False))
    _seed(db, scope='{"owner":"obj:user:other"}')
    assert svc.citable_claims(user=_user()) == []  # no cross-principal leakage


def test_gate_span_and_confidence(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    _seed(db)
    cites = svc.citable_claims(user=_user())
    assert cites[0].span is not None and cites[0].span.get("page") == 2
    assert cites[0].confidence.fact_tier is not None


def test_gate_proposed_claim_not_cited(db):
    svc = ClaimEvidenceService(SQLClaimStore(db), _FakePerm())
    _seed(db, confirm=False)  # PROPOSED only
    assert svc.citable_claims(user=_user()) == []
