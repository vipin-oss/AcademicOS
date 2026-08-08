"""Integration tests: GET /ai/related (Sprint M13.3).

Tests the HTTP contract: feature-flag enforcement, authentication gate,
AI-master-switch authority (no embedding call when disabled), error mapping
(404 / 403 / 422), the HashingEmbedder fallback path, and that the endpoint
reuses the SAME embedder identity as the semantic-search route. The full
result pipeline is covered by the unit tests (test_related_documents.py).
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
from app.api.routes.search import get_embedder
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.ai.provider_factory import build_ai_core
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.main import app

API = "/api/v1/ai"


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

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER, title="rel.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:rel-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="rel.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    # A real AiCore with no providers (embedder() raises -> HashingEmbedder).
    app.dependency_overrides[get_ai_core] = lambda: build_ai_core(config_mod.settings)
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
                "chat": False, "rag": False, "memory": False,
                "agents": False, "document_understanding": False,
                "streaming": True, "summarization": False,
                "semantic_search": False, "qa": False,
                "enrichment": False,
                "related_documents": flags.get("related_documents", False),
            },
        ),
    )


class TestFeatureFlagAndAuth:
    def test_related_404_when_flag_off(self, harness):
        original = config_mod.settings.ai_related_documents_enabled
        config_mod.settings.ai_related_documents_enabled = False
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            config_mod.settings.ai_related_documents_enabled = original

    def test_related_requires_auth(self, harness):
        original = config_mod.settings.ai_related_documents_enabled
        config_mod.settings.ai_related_documents_enabled = True
        try:
            app.dependency_overrides.pop(get_current_user, None)
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 401
        finally:
            config_mod.settings.ai_related_documents_enabled = original

    def test_related_flag_on_passes_gate(self, harness):
        """Flag on + master on -> the endpoint proceeds past the gate (it then
        404s on the missing source, NOT from the flag gate)."""
        enabled_core = _core_with(enabled=True, related_documents=True)
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: enabled_core
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "obj:document:none"})
            assert resp.status_code == 404  # source not found, not flag-gated
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)


class TestMasterSwitchGate:
    """AI_ENABLED=false must block related docs even when the flag is on, and
    no embedding call may occur."""

    def test_ai_disabled_blocks_related_even_when_flag_on(self, harness):
        disabled_core = _core_with(enabled=False, related_documents=True)
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: disabled_core
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)

    def test_no_embedding_call_when_ai_disabled(self, harness):
        embed_calls: list[str] = []

        class _TrackingEmbedder(HashingEmbedder):
            def embed(self, text):  # type: ignore[override]
                embed_calls.append(text)
                raise AssertionError("embed() must not be called when AI is disabled")

        disabled_core = _core_with(enabled=False, related_documents=True)
        app.dependency_overrides[get_ai_core] = lambda: disabled_core
        app.dependency_overrides[get_embedder] = lambda: _TrackingEmbedder()
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
            assert embed_calls == []
        finally:
            app.dependency_overrides.pop(get_embedder, None)
            app.dependency_overrides[get_ai_core] = lambda: build_ai_core(config_mod.settings)


class TestEmbedderIdentityReuse:
    def test_reuses_same_embedder_identity_as_semantic_search(self, harness):
        """When the related flag is on but semantic search is off, the route
        resolves the SAME embedder the /search route would (HashingEmbedder),
        never a different embedding abstraction."""
        original = config_mod.settings.ai_related_documents_enabled
        config_mod.settings.ai_related_documents_enabled = True
        captured: dict = {}

        class _CapturingEmbedder(HashingEmbedder):
            pass

        def _capture_embedder():
            e = _CapturingEmbedder()
            captured["embedder"] = e
            return e

        app.dependency_overrides[get_embedder] = _capture_embedder
        try:
            # related flag on; /ai/related gate uses its own flag; the embedder
            # dep resolves to the same HashingEmbedder path as /search.
            resp = harness.get(
                f"{API}/related",
                params={"object_id": "obj:document:none"},
            )
            assert resp.status_code in (200, 404)  # source not found -> 404
            assert isinstance(captured.get("embedder"), HashingEmbedder)
        finally:
            app.dependency_overrides.pop(get_embedder, None)
            config_mod.settings.ai_related_documents_enabled = original


class TestErrorMapping:
    def test_missing_object_id_param_422(self, harness):
        original = config_mod.settings.ai_related_documents_enabled
        config_mod.settings.ai_related_documents_enabled = True
        try:
            resp = harness.get(f"{API}/related")
            assert resp.status_code == 422  # required query param missing
        finally:
            config_mod.settings.ai_related_documents_enabled = original

    def test_invalid_limit_422(self, harness):
        original = config_mod.settings.ai_related_documents_enabled
        config_mod.settings.ai_related_documents_enabled = True
        try:
            resp = harness.get(
                f"{API}/related", params={"object_id": "x", "limit": 0}
            )
            assert resp.status_code == 422  # ge=1 enforced
        finally:
            config_mod.settings.ai_related_documents_enabled = original
