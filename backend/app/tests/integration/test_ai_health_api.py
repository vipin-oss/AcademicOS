"""Integration tests: AI health endpoints (Sprint M11.1).

Covers the full DI chain: settings -> provider config parsing -> registry
-> placeholder gateways -> AiCore -> routes. The AI surface is
infrastructure-only: /ai/health is public, /ai/providers and /ai/models
are authenticated; JSON-only responses.
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
from app.infrastructure.ai.provider_factory import build_ai_core
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.main import app


class _AiSettings:
    """Settings stand-in with M11.1 AI fields (no env mutation needed)."""

    ai_enabled = True
    ai_default_provider = "local"
    ai_default_model = ""
    ai_temperature = 0.0
    ai_max_tokens = 2048
    ai_timeout_seconds = 30.0
    ai_streaming_enabled = True
    ai_chat_enabled = False
    ai_rag_enabled = False
    ai_memory_enabled = False
    ai_agents_enabled = False
    ai_document_understanding_enabled = False
    ai_providers_json = ""


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="ai.test",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:ai-test-user-0001"),
    )
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _override_core(settings: _AiSettings | None = None):
    core = build_ai_core(settings or _AiSettings())
    app.dependency_overrides[get_ai_core] = lambda: core


class TestAiHealthPublic:
    def test_health_is_public_and_reports_not_configured(self, client):
        _override_core()
        resp = client.get("/api/v1/ai/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "not_configured"
        assert body["ai_enabled"] is True
        assert body["default_provider"] == "local"
        assert body["default_provider_valid"] is False  # M11.3.1: no provider is actually executable
        assert body["providers_total"] == 5
        assert body["providers_configured"] == 0
        assert body["feature_flags"]["rag"] is False
        assert body["feature_flags"]["streaming"] is True
        assert body["checked_at"]

    def test_health_disabled_when_ai_enabled_false(self, client):
        settings = _AiSettings()
        settings.ai_enabled = False
        _override_core(settings)
        body = client.get("/api/v1/ai/health").json()
        assert body["status"] == "disabled"
        assert body["ai_enabled"] is False

    def test_health_error_on_unknown_default_provider(self, client):
        settings = _AiSettings()
        settings.ai_default_provider = "oepnai"
        _override_core(settings)
        body = client.get("/api/v1/ai/health").json()
        assert body["status"] == "error"
        assert body["default_provider_valid"] is False

    def test_health_ok_when_provider_configured(self, client):
        settings = _AiSettings()
        settings.ai_default_provider = "openai"
        settings.ai_providers_json = (
            '[{"provider_id": "openai", "kind": "openai", "model": "gpt-4o-mini"}]'
        )
        # A configured row alone still yields not_configured in M11.1 (the
        # model is declared but no adapter is wired): health stays honest.
        _override_core(settings)
        body = client.get("/api/v1/ai/health").json()
        assert body["status"] == "not_configured"
        assert body["providers_total"] == 5


class TestAiProvidersAuthenticated:
    def test_providers_requires_auth(self, client):
        _override_core()
        # Remove the fixture's auth override: the real bearer gate applies.
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/api/v1/ai/providers").status_code == 401

    def test_providers_lists_catalogue_in_order(self, client):
        _override_core()
        resp = client.get("/api/v1/ai/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert [p["provider_id"] for p in body["items"]] == [
            "openai",
            "anthropic",
            "google",
            "ollama",
            "local",
        ]
        for provider in body["items"]:
            assert provider["status"] == "not_configured"
            assert provider["configured"] is False
            assert provider["display_name"]
            assert "not configured" in provider["detail"]

    def test_providers_show_declared_models(self, client):
        # One row per catalogue kind; the config entry's provider_id is an
        # alias carried on the declared model, not the row identity.
        settings = _AiSettings()
        settings.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini"}]'
        )
        _override_core(settings)
        body = client.get("/api/v1/ai/providers").json()
        # M11.3.1: the row identity is the provider_id ("oa"); kind distinguishes the family.
        openai = next(p for p in body["items"] if p["kind"] == "openai")
        assert openai["provider_id"] == "oa"
        assert openai["models"][0]["model_id"] == "gpt-4o-mini"
        assert openai["models"][0]["provider_id"] == "oa"
        assert openai["models"][0]["configured"] is False
        assert openai["status"] == "not_configured"


class TestAiModelsAuthenticated:
    def test_models_requires_auth(self, client):
        _override_core()
        # Remove the fixture's auth override: the real bearer gate applies.
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/api/v1/ai/models").status_code == 401

    def test_models_empty_by_default(self, client):
        _override_core()
        body = client.get("/api/v1/ai/models").json()
        assert body["default_provider"] == "local"
        assert body["default_model"] == ""
        assert body["models"] == []

    def test_models_aggregate_declared_models(self, client):
        settings = _AiSettings()
        settings.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini"},'
            ' {"provider_id": "lc", "kind": "local", "model": "qwen2.5:7b"}]'
        )
        _override_core(settings)
        body = client.get("/api/v1/ai/models").json()
        assert [m["model_id"] for m in body["models"]] == ["gpt-4o-mini", "qwen2.5:7b"]


class TestAiRegression:
    def test_existing_health_endpoint_unchanged(self, client):
        # The M11.1 wiring must not disturb the M1 health probe.
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ai_router_is_json_only(self, client):
        # No HTML/docs surface is added by the AI router.
        _override_core()
        assert client.get("/api/v1/ai/health").headers["content-type"].startswith(
            "application/json"
        )
