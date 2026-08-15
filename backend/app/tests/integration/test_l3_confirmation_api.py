"""L3 confirmation API integration tests (ADR-022/032/033)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
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
        object_type=ObjectType.USER, title="test.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:reviewer-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"
SCOPE = '{"owner":"obj:user:reviewer-0001","readers":[],"writers":[],"managers":[]}'


def test_propose_then_approve_via_api(client: TestClient):
    r = client.post(f"{API}/claims", json={
        "predicate_id": "sanctioned_amount", "raw_value": "₹5000",
        "source_text": "5000", "source_document_id": "obj:document:1",
        "source_version": 1, "spans": [], "acl_scope": SCOPE,
        "fact_confidence": 0.5,
    })
    assert r.status_code == 201, r.text
    claim_id = r.json()["claim_id"]

    pending = client.get(f"{API}/confirmations/pending")
    assert any(p["claim_id"] == claim_id for p in pending.json())

    appr = client.post(f"{API}/confirmations/{claim_id}/approve?notes=ok")
    assert appr.status_code == 200, appr.text
    assert appr.json()["decision"] == "approve"

    decisions = client.get(f"{API}/confirmations/{claim_id}/decisions")
    assert len(decisions.json()) == 1


def test_correct_via_api(client: TestClient):
    r = client.post(f"{API}/claims", json={
        "predicate_id": "issue_date", "raw_value": "2026-01-01",
        "source_text": "date", "source_document_id": "obj:document:1",
        "source_version": 1, "spans": [], "acl_scope": SCOPE,
    })
    claim_id = r.json()["claim_id"]
    corr = client.post(f"{API}/confirmations/{claim_id}/correct",
                       json={"raw_value": "2026-08-13", "notes": "corrected"})
    assert corr.status_code == 200, corr.text
    assert corr.json()["decision"] == "correct"


def test_reject_then_not_in_pending(client: TestClient):
    r = client.post(f"{API}/claims", json={
        "predicate_id": "principal_investigator", "raw_value": "Dr X",
        "source_text": "PI", "source_document_id": "obj:document:1",
        "source_version": 1, "spans": [], "acl_scope": SCOPE,
    })
    claim_id = r.json()["claim_id"]
    rej = client.post(f"{API}/confirmations/{claim_id}/reject")
    assert rej.status_code == 200
    pending = client.get(f"{API}/confirmations/pending")
    assert all(p["claim_id"] != claim_id for p in pending.json())


def test_cdm_confirm_via_api(client: TestClient):
    r = client.post(f"{API}/confirmations/cdm/block:1/approve")
    assert r.status_code == 200, r.text
    assert r.json()["resulting_status"] == "confirmed"
