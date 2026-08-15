"""Integration tests: POST /ai/assistants/* and GET /ai/assistants (M22-M25).

Tests the HTTP contract: feature-flag enforcement (``AI_ASSISTANTS_ENABLED``),
authentication gate, AI-master-switch authority, unknown-role 422, request
validation, the teaching academic-integrity refusal path, and the role
catalogue. The full grounded pipeline is covered by the unit tests
(test_domain_assistant.py) and the shared QA tests.
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
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.main import app

API = "/api/v1/ai"


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        ObjectType.USER, "asst.api.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:asst-api-00000001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="asst.api.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _core_with(**flags):
    from app.application.ai.config import AiConfigView
    from app.application.ai.core import AiCore
    from app.application.ai.providers.registry import ProviderRegistry

    return AiCore(
        registry=ProviderRegistry(),
        gateways={},
        config=AiConfigView(
            enabled=flags.get("enabled", True),
            default_provider="local",
            default_model="",
            temperature=0.0,
            max_tokens=2048,
            timeout_seconds=30.0,
            streaming_enabled=True,
            feature_flags={
                "chat": False,
                "rag": False, "memory": False,
                "agents": False, "document_understanding": False,
                "streaming": True, "summarization": False,
                "semantic_search": False, "qa": False,
                "enrichment": False, "related_documents": False,
                "assistants": flags.get("assistants", False),
            },
        ),
    )


class TestFeatureFlagAndAuth:
    def test_assistant_404_when_flag_off(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=False)
        resp = harness.post(f"{API}/assistants/research", json={"message": "hi"})
        assert resp.status_code == 404

    def test_master_switch_off_blocks_even_when_flag_on(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=False, assistants=True)
        resp = harness.post(f"{API}/assistants/research", json={"message": "hi"})
        assert resp.status_code == 404

    def test_stream_404_when_flag_off(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=False)
        resp = harness.post(f"{API}/assistants/research/stream", json={"message": "hi"})
        assert resp.status_code == 404

    def test_requires_auth(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = harness.post(f"{API}/assistants/research", json={"message": "hi"})
            assert resp.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: UniversalObject.create(
                ObjectType.USER, "asst.api.test", created_by="system",
                status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:asst-api-00000001"),
            )


class TestRequestValidation:
    def test_unknown_role_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(f"{API}/assistants/cooking", json={"message": "hi"})
        assert resp.status_code == 422

    def test_missing_message_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(f"{API}/assistants/research", json={})
        assert resp.status_code == 422

    def test_unknown_field_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(f"{API}/assistants/research", json={"message": "hi", "bogus": 1})
        assert resp.status_code == 422


class TestTeachingIntegrityRefusal:
    """The teaching academic-integrity guard (F19.3 / A11) at the HTTP layer."""

    def test_assessable_request_refused_without_error(self, harness):
        """A completion request returns 200 with a refusal (available=True),
        NOT an error and NOT a generated submission."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(
            f"{API}/assistants/teaching",
            json={"message": "please write my essay on photosynthesis"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "teaching"
        assert body["available"] is True
        assert body["citations"] == []
        lowered = body["answer"].lower()
        assert "can't" in lowered or "cannot" in lowered

    def test_legit_teaching_request_proceeds(self, harness):
        """An explain/quiz request reaches the pipeline (empty gateway -> honest
        fallback), it is NOT refused by the guard."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(
            f"{API}/assistants/teaching",
            json={"message": "explain mitosis at an introductory level"},
        )
        assert resp.status_code == 200
        # No real gateway wired -> honest unavailable fallback.
        assert resp.json()["available"] is False


class TestEnabledPath:
    def test_research_enabled_fallback_when_no_gateway(self, harness):
        """Enabled + no real gateway -> honest fallback answer (available=False), 200."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(f"{API}/assistants/research", json={"message": "what gaps exist?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "research"
        assert body["available"] is False

    def test_history_accepted(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=True)
        resp = harness.post(
            f"{API}/assistants/publication",
            json={
                "message": "polish this",
                "history": [
                    {"role": "user", "content": "draft intro"},
                    {"role": "assistant", "content": "here is a draft"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "publication"


class TestCatalogue:
    def test_list_roles_returns_four(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, assistants=False)
        resp = harness.get(f"{API}/assistants")
        assert resp.status_code == 200
        keys = {r["key"] for r in resp.json()["items"]}
        assert keys == {"research", "teaching", "publication", "administration"}

    def test_catalogue_requires_auth(self, harness):
        app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = harness.get(f"{API}/assistants")
            assert resp.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: UniversalObject.create(
                ObjectType.USER, "asst.api.test", created_by="system",
                status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:asst-api-00000001"),
            )
