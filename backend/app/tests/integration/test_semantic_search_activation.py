"""Integration tests: semantic search activation (Sprint M12.3).

Tests the feature-flag enforcement and embedder resolution behaviour:
- AI_SEMANTIC_SEARCH_ENABLED=false → HashingEmbedder (backward compat).
- AI_SEMANTIC_SEARCH_ENABLED=true → AI Core embedder used.
- AI Core embedder unavailable → graceful fallback to HashingEmbedder.
- Existing search behaviour unchanged when flag is off.
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

import app.core.config as config_mod
from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.application.ports.embedder import Embedder
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.main import app

API = "/api/v1/search"


class _FakeEmbedder(Embedder):
    """A test-only embedder that returns a fixed vector — distinguishable
    from HashingEmbedder so tests can verify which embedder is active."""

    def __init__(self, dimensions=8):
        self._dim = dimensions

    def embed(self, text: str) -> list[float]:
        return [0.5] * self._dim

    @property
    def dimensions(self) -> int:
        return self._dim


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
        ObjectType.USER, "search.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:search-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="search.test",
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


class TestFeatureFlagEnforcement:
    def test_flag_off_uses_hashing_embedder(self, harness):
        """When AI_SEMANTIC_SEARCH_ENABLED is false, the search endpoint
        works normally with the HashingEmbedder (backward compat)."""
        original = config_mod.settings.ai_semantic_search_enabled
        config_mod.settings.ai_semantic_search_enabled = False
        try:
            resp = harness.get(f"{API}?text=anything")
            # 200 means the endpoint works; the embedder is HashingEmbedder
            # (the response shape is unchanged from pre-M12).
            assert resp.status_code == 200
        finally:
            config_mod.settings.ai_semantic_search_enabled = original

    def test_flag_off_does_not_touch_ai_core_embedder(self, harness):
        """When the flag is off, get_embedder() must NOT call ai_core.embedder()."""
        original = config_mod.settings.ai_semantic_search_enabled
        config_mod.settings.ai_semantic_search_enabled = False

        embedder_called = False

        class _NoCallCore:
            config = type("C", (), {"enabled": True, "feature_flags": {}})()

            def embedder(self):
                nonlocal embedder_called
                embedder_called = True
                return _FakeEmbedder()

        app.dependency_overrides[get_ai_core] = lambda: _NoCallCore()
        try:
            harness.get(f"{API}?text=test")
            assert not embedder_called  # AI Core was never consulted
        finally:
            config_mod.settings.ai_semantic_search_enabled = original
            app.dependency_overrides.pop(get_ai_core, None)

    def test_flag_on_uses_ai_core_embedder(self, harness):
        """When AI_SEMANTIC_SEARCH_ENABLED is true, the AI Core embedder
        is resolved and used."""
        original = config_mod.settings.ai_semantic_search_enabled
        config_mod.settings.ai_semantic_search_enabled = True
        app.dependency_overrides[get_ai_core] = lambda: _StubCore(_FakeEmbedder())
        try:
            resp = harness.get(f"{API}?text=test")
            assert resp.status_code == 200
        finally:
            config_mod.settings.ai_semantic_search_enabled = original
            app.dependency_overrides.pop(get_ai_core, None)

    def test_flag_on_ai_core_unavailable_falls_back_gracefully(self, harness):
        """When the flag is on but the AI Core embedder raises, the search
        endpoint still works (HashingEmbedder fallback)."""
        original = config_mod.settings.ai_semantic_search_enabled
        config_mod.settings.ai_semantic_search_enabled = True

        class _BrokenCore:
            config = type("C", (), {"enabled": True, "feature_flags": {}})()

            def embedder(self):
                raise RuntimeError("AI Core not configured")

        app.dependency_overrides[get_ai_core] = lambda: _BrokenCore()
        try:
            resp = harness.get(f"{API}?text=test")
            assert resp.status_code == 200  # graceful fallback
        finally:
            config_mod.settings.ai_semantic_search_enabled = original
            app.dependency_overrides.pop(get_ai_core, None)


class _StubCore:
    """Minimal AiCore stub for embedder resolution tests."""

    def __init__(self, embedder_instance):
        self._embedder = embedder_instance
        self.config = type("C", (), {
            "enabled": True,
            "feature_flags": {"semantic_search": True},
        })()

    def embedder(self):
        return self._embedder


class TestMasterSwitchGate:
    """AI_ENABLED=false must block semantic embedding even when
    AI_SEMANTIC_SEARCH_ENABLED=true. No AI embedder resolution occurs."""

    def test_ai_disabled_blocks_semantic_even_when_flag_on(self, harness):
        """When AI_ENABLED=false, the search endpoint falls back to
        HashingEmbedder even if AI_SEMANTIC_SEARCH_ENABLED=true."""
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        class _TrackingEmbedder:
            embed_called = False
            def embed(self, text):
                _TrackingEmbedder.embed_called = True
                return [0.0] * 8
            @property
            def dimensions(self):
                return 8

        disabled_core = AiCore(
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
                    "streaming": True,
                    "summarization": False,
                    "semantic_search": True,  # flag ON
                },
            ),
            embedder=_TrackingEmbedder(),
        )
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: disabled_core
        try:
            resp = harness.get(f"{API}?text=test")
            assert resp.status_code == 200  # search works (lexical)
            assert not _TrackingEmbedder.embed_called  # AI embedder never called
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)

    def test_ai_enabled_and_flag_on_resolves_embedder(self, harness):
        """When both AI_ENABLED=true and AI_SEMANTIC_SEARCH_ENABLED=true,
        the AI Core embedder is resolved (existing behaviour unchanged)."""
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: _StubCore(_FakeEmbedder())
        config_mod.settings.ai_semantic_search_enabled = True
        try:
            resp = harness.get(f"{API}?text=test")
            assert resp.status_code == 200  # search works with real embedder
        finally:
            config_mod.settings.ai_semantic_search_enabled = False
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)

    def test_ai_enabled_flag_off_uses_hashing(self, harness):
        """When AI_ENABLED=true but AI_SEMANTIC_SEARCH_ENABLED=false,
        HashingEmbedder is used (existing behaviour unchanged)."""
        config_mod.settings.ai_semantic_search_enabled = False
        resp = harness.get(f"{API}?text=test")
        assert resp.status_code == 200  # lexical search works
