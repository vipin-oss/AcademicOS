"""Integration tests: GET /search read-time repair (Sprint M14.1).

Reproduces the reported "no results" symptom: objects exist in the store but
the derived ``search_documents`` projection is empty because the outbox was
never drained (the system ships no always-on relay). The read-time repair in
``GET /search`` drains pending events before querying, so a newly created
document is searchable WITHOUT a manual ``/search/index/sync``.

These tests create a document directly in the store (with its outbox events,
exactly as the document-creation use case does) and then exercise the real
HTTP endpoint.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_user
from app.application.services.outbox import to_outbox_row
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.main import app

API = "/api/v1/search"


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    user = UniversalObject.create(
        ObjectType.USER, "search.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:search-usr-0001"),
    )
    session.add(ObjectModel(
        id=str(user.id), object_type="user", title="search.user",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, session, user
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _create_document(session, *, title: str, doc_id: str, owner_id: str) -> None:
    """Create a document exactly as the creation use case does: build the
    aggregate, pop its domain events, persist them as durable outbox rows so
    the read-time repair can drain them into the search projection."""
    repo = SQLAlchemyObjectRepository(session)
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, title, created_by=owner_id,
        object_id=ObjectId(doc_id), status=ObjectStatus.ACTIVE,
    )
    outbox_rows = [to_outbox_row(e) for e in doc.pop_domain_events()]
    repo.save(doc, outbox_events=outbox_rows)
    session.commit()


class TestSearchReadRepair:
    def test_new_document_is_searchable_without_manual_sync(self, harness):
        """The reported symptom: a document exists but search returns nothing.
        With read-time repair the outbox is drained on search, so the document
        is found immediately (no /search/index/sync required)."""
        client, session, user = harness
        _create_document(
            session, title="Renewable Energy Systems",
            doc_id="obj:document:energy-0001", owner_id=str(user.id),
        )

        resp = client.get(API, params={"text": "energy"})

        assert resp.status_code == 200
        ids = [r["object_id"] for r in resp.json()["results"]]
        assert "obj:document:energy-0001" in ids

    def test_matching_by_title_substring(self, harness):
        client, session, user = harness
        _create_document(
            session, title="Photovoltaic Cell Efficiency",
            doc_id="obj:document:pv-0001", owner_id=str(user.id),
        )
        resp = client.get(API, params={"text": "photovoltaic"})
        assert resp.status_code == 200
        assert any(r["object_id"] == "obj:document:pv-0001" for r in resp.json()["results"])

    def test_non_matching_query_returns_clean_empty(self, harness):
        """Empty results are a clean empty list — NOT an error and NOT 'cancelled'."""
        client, session, user = harness
        _create_document(
            session, title="Renewable Energy Systems",
            doc_id="obj:document:energy-0002", owner_id=str(user.id),
        )
        resp = client.get(API, params={"text": "zzznomatchzzz"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_repeated_search_is_stable(self, harness):
        """A second search (after the first drained the outbox) is stable."""
        client, session, user = harness
        _create_document(
            session, title="Renewable Energy Systems",
            doc_id="obj:document:energy-0003", owner_id=str(user.id),
        )
        first = client.get(API, params={"text": "energy"}).json()["results"]
        second = client.get(API, params={"text": "energy"}).json()["results"]
        assert {r["object_id"] for r in first} == {r["object_id"] for r in second}
        assert "obj:document:energy-0003" in {r["object_id"] for r in second}

    def test_repair_does_not_break_search_when_outbox_empty(self, harness):
        """No pending events — repair is a no-op and search still works."""
        client, _session, _user = harness
        resp = client.get(API, params={"text": "anything"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []
