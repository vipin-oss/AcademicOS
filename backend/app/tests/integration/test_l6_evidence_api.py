"""L6 evidence API integration tests (ADR-022 / ADR-039)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user
from app.application.services.claim_service import ClaimService
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.session import get_db
from app.main import app
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore


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
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:l6-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user

    # seed a CONFIRMED claim
    claims = ClaimService(SQLClaimStore(session))
    claim = claims.propose(
        predicate_id="sanctioned_amount", raw_value=5000, source_text="amt",
        source_document_id="obj:document:1", source_version=1,
        spans=[Span(kind=SpanKind.PAGE, source_id="obj:document:1", page=1)],
        acl_scope='{"owner":"obj:user:l6-0001"}', fact_confidence=0.9,
    )
    claims.confirm(claim.claim_id, reviewer="obj:user:l6-0001", assert_human=True)
    session.commit()

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def test_citable_returns_confirmed_claim(client: TestClient):
    r = client.get(f"{API}/evidence/citable")
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(c["predicate_id"] == "sanctioned_amount" for c in body)
    assert body[0]["span"]["page"] == 1
    assert body[0]["confidence"]["fact_tier"] in ("high", "medium", "low")
