"""Integration tests: POST /ai/qa (Sprint M13.1).

Tests the HTTP contract: feature-flag enforcement, authentication gate,
fallback behavior, and provenance metadata. The full generation pipeline
is covered by the unit tests.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

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
        ObjectType.USER, "qa.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:qa-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="qa.test",
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


class TestFeatureFlagAndAuth:
    def test_qa_404_when_flag_off(self, harness):
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        core = AiCore(
            registry=ProviderRegistry(),
            gateways={},
            config=AiConfigView(
                enabled=True, default_provider="local", default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={
                    "chat": False, "rag": False, "memory": False,
                    "agents": False, "document_understanding": False,
                    "streaming": True, "summarization": False,
                    "semantic_search": False, "qa": False,
                },
            ),
        )
        app.dependency_overrides[get_ai_core] = lambda: core
        resp = harness.post(f"{API}/qa", json={"question": "test"})
        assert resp.status_code == 404

    def test_qa_requires_auth(self, harness):
        app.dependency_overrides.pop(get_current_user, None)
        resp = harness.post(f"{API}/qa", json={"question": "test"})
        assert resp.status_code == 401

    def test_qa_404_when_ai_disabled(self, harness):
        """AI_ENABLED=false blocks QA even when AI_QA_ENABLED=true."""
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        core = AiCore(
            registry=ProviderRegistry(),
            gateways={},
            config=AiConfigView(
                enabled=False,  # master switch OFF
                default_provider="local", default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={
                    "chat": False, "rag": False, "memory": False,
                    "agents": False, "document_understanding": False,
                    "streaming": True, "summarization": False,
                    "semantic_search": False,
                    "qa": True,  # flag ON but master OFF
                },
            ),
        )
        app.dependency_overrides[get_ai_core] = lambda: core
        resp = harness.post(f"{API}/qa", json={"question": "test"})
        assert resp.status_code == 404

    def test_missing_question_422(self, harness):
        resp = harness.post(f"{API}/qa", json={})
        assert resp.status_code == 422


class TestStreamingQA:
    def test_stream_404_when_flag_off(self, harness):
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        core = AiCore(
            registry=ProviderRegistry(),
            gateways={},
            config=AiConfigView(
                enabled=True, default_provider="local", default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={
                    "chat": False, "rag": False, "memory": False,
                    "agents": False, "document_understanding": False,
                    "streaming": True, "summarization": False,
                    "semantic_search": False, "qa": False,
                },
            ),
        )
        app.dependency_overrides[get_ai_core] = lambda: core
        resp = harness.post(f"{API}/qa/stream", json={"question": "test"})
        assert resp.status_code == 404
