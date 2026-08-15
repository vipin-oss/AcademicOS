"""L3 confirmation queue tests (ADR-033): triage + ACL filtering."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.services.confirmation_queue import ConfirmationQueue
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
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


def _propose(db, *, pred="sanctioned_amount", value, conf, scope):
    return ClaimService(SQLClaimStore(db)).propose(
        predicate_id=pred, raw_value=value, source_text="t",
        source_document_id="obj:document:1", source_version=1, spans=[], acl_scope=scope,
        fact_confidence=conf,
    )


def test_queue_acl_filters_out_other_scopes(db):
    _propose(db, value=1, conf=0.5, scope='{"owner":"u:1"}')
    _propose(db, value=2, conf=0.5, scope='{"owner":"u:9"}')  # other owner
    q = ConfirmationQueue(SQLClaimStore(db))
    items = q.pending(can_decide=lambda scope: "u:1" in (scope or ""))
    assert len(items) == 1
    assert items[0].acl_scope == '{"owner":"u:1"}'


def test_queue_excludes_when_no_access(db):
    _propose(db, value=1, conf=0.5, scope='{"owner":"u:1"}')
    q = ConfirmationQueue(SQLClaimStore(db))
    items = q.pending(can_decide=lambda scope: False)
    assert items == []


def test_queue_pagination(db):
    for i in range(5):
        _propose(db, value=i, conf=0.5, scope='{"owner":"u:1"}')
    q = ConfirmationQueue(SQLClaimStore(db))
    page1 = q.pending(page=1, page_size=2, can_decide=lambda s: True)
    page2 = q.pending(page=2, page_size=2, can_decide=lambda s: True)
    assert len(page1) == 2 and len(page2) == 2
