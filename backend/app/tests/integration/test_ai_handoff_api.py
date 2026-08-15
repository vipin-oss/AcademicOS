"""Integration tests: POST /ai/handoff (Sprint M16 — external-AI handoff).

Tests the HTTP contract: authentication, the deliberate NO-AI-FLAG gate (the
handoff is the free fallback and must work with AI disabled), request
validation (422), and that the success response carries a grounded,
copyable prompt bundle with only readable sources.
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

from app.api.dependencies.ai import get_ai_core
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

API = "/api/v1/ai"


def _core(enabled: bool):
    from app.application.ai.config import AiConfigView
    from app.application.ai.core import AiCore
    from app.application.ai.providers.registry import ProviderRegistry

    return AiCore(
        registry=ProviderRegistry(),
        gateways={},
        config=AiConfigView(
            enabled=enabled,
            default_provider="local", default_model="",
            temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
            streaming_enabled=True,
            feature_flags={
                "chat": False, "rag": False, "memory": False,
                "agents": False, "document_understanding": False,
                "streaming": True, "summarization": False,
                "semantic_search": False, "qa": False,
                "enrichment": False, "related_documents": False,
            },
        ),
    )


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
        ObjectType.USER, "handoff.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:handoff-0001"),
    )
    session.add(ObjectModel(
        id=str(user.id), object_type="user", title="handoff.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    # A document the user owns (READ allowed) so retrieval can find it.
    repo = SQLAlchemyObjectRepository(session)
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "Renewable Energy Report", created_by=str(user.id),
        object_id=ObjectId("obj:document:energy-0001"), status=ObjectStatus.ACTIVE,
    )
    repo.save(doc, outbox_events=[to_outbox_row(e) for e in doc.pop_domain_events()])
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class TestAuthAndGate:
    def test_handoff_requires_auth(self, harness):
        app.dependency_overrides.pop(get_current_user, None)
        resp = harness.post(f"{API}/handoff", json={"question": "x"})
        assert resp.status_code == 401

    def test_handoff_works_with_AI_DISABLED(self, harness):
        """The handoff is the no-provider / no-cost path: it must NOT be gated
        on AI_ENABLED (its purpose is to work without AI)."""
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=False)
        resp = harness.post(f"{API}/handoff", json={"question": "energy"})
        assert resp.status_code == 200

    def test_handoff_works_with_AI_ENABLED(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=True)
        resp = harness.post(f"{API}/handoff", json={"question": "energy"})
        assert resp.status_code == 200


class TestValidation:
    def test_empty_question_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=False)
        resp = harness.post(f"{API}/handoff", json={"question": "  "})
        assert resp.status_code == 422

    def test_unsupported_task_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=False)
        resp = harness.post(f"{API}/handoff", json={"task": "summarize", "question": "x"})
        assert resp.status_code == 422

    def test_unknown_field_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=False)
        resp = harness.post(f"{API}/handoff", json={"question": "x", "bogus": 1})
        assert resp.status_code == 422


class TestSuccessBundle:
    def test_returns_grounded_copyable_bundle(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core(enabled=False)
        resp = harness.post(f"{API}/handoff", json={"question": "energy"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["task"] == "qa"
        assert body["system_prompt"]
        assert body["user_prompt"]
        assert body["combined_prompt"]
        assert body["expected_format"]
        assert body["instructions"]
        # The document the user can READ appears as a source.
        titles = {s["title"] for s in body["sources"]}
        assert "Renewable Energy Report" in titles
        # The no-cost note is present.
        assert "no cost" in body["note"].lower() or "no charge" in body["note"].lower()
