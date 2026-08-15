"""V3 ADR-067 document-intake API tests (upload -> analyze endpoint)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    def _override_db():
        yield session

    user = UniversalObject.create(
        ObjectType.USER, "intake.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:intake-0001"),
    )
    session.add(ObjectModel(
        id=str(user.id), object_type="user", title="intake.user", status="active",
        version=1, metadata_json=[], audit_json={"created_by": "system"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_analyze_upload_end_to_end(client):
    pdf = b"%PDF-1.4\n%fake\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td (Conference: ICVPI) Tj ET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\ntrailer\n<< /Root 1 0 R /Size 6 >>\n%%EOF\n"
    resp = client.post(
        "/api/v1/documents/analyze-upload",
        data={"title": "conf.pdf", "document_type": "pdf"},
        files={"file": ("conference.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "document_id" in body
    assert body["status"] in ("unknown", "review_required", "ingested")


def test_analyze_missing_document_404(client):
    resp = client.post("/api/v1/documents/obj:document:nope/analyze")
    assert resp.status_code == 404
