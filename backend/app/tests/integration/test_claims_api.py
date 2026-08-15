"""L1 claims / CDM / confirmations API integration tests (ADR-022 OpenAPI)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user
from app.infrastructure.db.session import get_db
from app.main import app
from app.infrastructure.db.models.object_model import Base
# register L1 tables
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401


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
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def test_propose_and_confirm_claim(client: TestClient):
    r = client.post(f"{API}/claims", json={
        "predicate_id": "sanctioned_amount",
        "raw_value": "₹10,00,000",
        "source_text": "Sanctioned ten lakh.",
        "source_document_id": "obj:document:1",
        "source_version": 1,
        "spans": [{"kind": "page", "source_id": "obj:document:1", "page": 2}],
        "fact_confidence": 0.9,
    })
    assert r.status_code == 201, r.text
    claim = r.json()
    assert claim["status"] == "proposed"
    assert claim["value_schema"] == "money"
    assert claim["value"]["amount"] == 1000000.0
    assert claim["spans"][0]["page"] == 2

    cid = claim["claim_id"]
    pending = client.get(f"{API}/confirmations/pending")
    assert any(p["claim_id"] == cid for p in pending.json())

    conf = client.post(f"{API}/claims/{cid}/confirm")
    assert conf.status_code == 200
    assert conf.json()["status"] == "confirmed"
    assert conf.json()["provenance"] == "asserted"


def test_unknown_predicate_raw_kept(client: TestClient):
    r = client.post(f"{API}/claims", json={
        "predicate_id": "bogus", "raw_value": "x", "source_text": "t",
        "source_document_id": "obj:document:1", "source_version": 1, "spans": [],
    })
    assert r.status_code == 201
    assert r.json()["value_schema"] == "raw"
    assert r.json()["value"]["reason"] == "unknown_predicate"


def test_claim_not_found(client: TestClient):
    r = client.get(f"{API}/claims/claim:missing")
    assert r.status_code == 404


def test_cdm_write_and_read(client: TestClient):
    r = client.post(f"{API}/cdm/documents/obj:document:1", json={
        "version": 1,
        "acl_scope": '{"owner":"u:1"}',
        "blocks": [
            {"block_type": "heading", "order": 0, "payload": {"text": "Title"}},
            {"block_type": "equation", "order": 1, "payload": {"formula": "E=mc^2"}},
        ],
    })
    assert r.status_code == 201, r.text
    assert r.json()["written"] == 2

    out = client.get(f"{API}/cdm/documents/obj:document:1")
    assert out.status_code == 200
    types = [b["block_type"] for b in out.json()]
    assert types == ["heading", "equation"]
