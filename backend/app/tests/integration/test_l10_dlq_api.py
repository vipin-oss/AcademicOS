"""L10 DLQ API integration tests (ADR-048)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
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
    repo = SQLAlchemyObjectRepository(session)

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="u:1", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:l10a-1"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    repo.save(fake_user)
    session.commit()
    with TestClient(app) as c:
        yield c, repo, session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_dead_letter_endpoint_empty(client):
    c, _repo, _session = client
    r = c.get("/api/v1/intake/dead-letter")
    assert r.status_code == 200
    body = r.json()
    assert body["sessions"] == [] and body["items"] == [] and body["total"] == 0


def test_dead_letter_endpoint_surfaces_failed(client):
    c, repo, session = client
    # seed a FAILED intake session
    from app.domain.value_objects.metadata import MetadataEntry
    from app.domain.value_objects.enums import MetadataLayer, Provenance
    from app.domain.value_objects.enums import ObjectType as OT

    s = UniversalObject.create(
        OT.INTAKE_SESSION, "failed-session", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:intake_session:l10a-1"),
    )
    s.set_metadata(
        MetadataEntry("intake.status", "failed", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="intake",
    )
    repo.save(s)
    session.commit()
    r = c.get("/api/v1/intake/dead-letter")
    assert r.status_code == 200
    body = r.json()
    assert any(e["kind"] == "session" and e["resumable"] for e in body["sessions"])
