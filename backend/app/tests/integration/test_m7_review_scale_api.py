"""V3 M7 review-at-scale API integration tests (ADR-054)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.application.services.claim_service import ClaimService
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="reviewer", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:reviewer-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c, session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"
SCOPE = '{"owner":"obj:user:reviewer-0001","readers":[],"writers":[],"managers":[]}'


def _suggest(session, value, confidence=0.99):
    claim = ClaimService(SQLClaimStore(session)).suggest(
        predicate_id="sanctioned_amount", raw_value=value, source_text=value,
        source_document_id="obj:document:1", source_version=1, spans=[],
        acl_scope=SCOPE, fact_confidence=confidence,
    )
    session.commit()
    return claim


def test_bulk_confirm_all_endpoint(client):
    client, session = client
    c1 = _suggest(session, "1000")
    c2 = _suggest(session, "2000", confidence=0.80)  # below threshold
    c3 = _suggest(session, "3000")

    r = client.post(f"{API}/confirmations/suggested/confirm-all")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["confirmed"] == 2 and body["skipped"] == 1
    assert all(d["reviewer"] == "obj:user:reviewer-0001" for d in body["decisions"])

    store = SQLClaimStore(session)
    assert store.get(c1.claim_id)[0].status is ClaimStatus.CONFIRMED
    assert store.get(c3.claim_id)[0].status is ClaimStatus.CONFIRMED
    assert store.get(c2.claim_id)[0].status is ClaimStatus.AUTO_SUGGESTED


def test_health_endpoint_reports_corrections_and_conflicts(client):
    client, session = client
    # a correction (decision='correct')
    c = _suggest(session, "1000")
    client.post(f"{API}/confirmations/{c.claim_id}/correct",
                json={"raw_value": "5000", "notes": "wrong"})
    # a conflict: confirmed 777 vs proposed 888
    store = SQLClaimStore(session)
    service = ClaimService(store)
    confirmed = service.propose(
        predicate_id="sanctioned_amount", raw_value="777", source_text="777",
        source_document_id="obj:document:2", source_version=1, spans=[],
        acl_scope=SCOPE, fact_confidence=1.0,
    )
    service.confirm(confirmed.claim_id, assert_human=True)
    service.propose(
        predicate_id="sanctioned_amount", raw_value="888", source_text="888",
        source_document_id="obj:document:3", source_version=1, spans=[],
        acl_scope=SCOPE, fact_confidence=0.9,
    )
    session.commit()

    r = client.get(f"{API}/confirmations/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_corrections"] >= 1
    assert any(c["predicate_id"] == "sanctioned_amount" for c in body["conflicts"])
