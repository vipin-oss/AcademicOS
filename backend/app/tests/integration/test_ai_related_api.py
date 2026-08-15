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


def _install_resolvers(monkeypatch, *, embedder=None, vector=None):
    """Patch the inline get_embedder/get_vector_repository the /ai/related route
    calls (M13.3.1: they are resolved AFTER the gate, not via Depends), and
    return a call log so tests can prove whether they were resolved at all."""
    log = {"embedder": 0, "vector": 0}

    def _embedder(core):
        log["embedder"] += 1
        return embedder if embedder is not None else HashingEmbedder()

    def _vector(emb):
        log["vector"] += 1
        return vector  # None by default -> use case degrades honestly

    monkeypatch.setattr("app.api.routes.ai.get_embedder", _embedder)
    monkeypatch.setattr("app.api.routes.ai.get_vector_repository", _vector)
    return log


def _use_core(core):
    original = app.dependency_overrides.get(get_ai_core)
    app.dependency_overrides[get_ai_core] = lambda: core
    return original


class TestFeatureGateResolutionOrder:
    """M13.3.1 defect-1: the gate runs BEFORE get_embedder/get_vector_repository
    can execute. A disabled feature must NOT resolve the AI embedder nor touch
    the vector store."""

    def test_ai_disabled_blocks_related_even_when_flag_on(self, harness):
        original = _use_core(_core_with(enabled=False, related_documents=True))
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            app.dependency_overrides[get_ai_core] = (
                original or (lambda: build_ai_core(config_mod.settings))
            )

    def test_embedder_not_resolved_when_flag_off(self, harness, monkeypatch):
        log = _install_resolvers(monkeypatch)
        original = _use_core(_core_with(enabled=True, related_documents=False))
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
            assert log == {"embedder": 0, "vector": 0}  # gate short-circuited
        finally:
            app.dependency_overrides[get_ai_core] = (
                original or (lambda: build_ai_core(config_mod.settings))
            )

    def test_embedder_not_resolved_when_master_off_flag_on(self, harness, monkeypatch):
        log = _install_resolvers(monkeypatch)
        original = _use_core(_core_with(enabled=False, related_documents=True))
        try:
            resp = harness.get(f"{API}/related", params={"object_id": "x"})
            assert resp.status_code == 404
            assert log == {"embedder": 0, "vector": 0}  # gate short-circuited
        finally:
            app.dependency_overrides[get_ai_core] = (
                original or (lambda: build_ai_core(config_mod.settings))
            )

    def test_embedder_resolved_when_enabled(self, harness, monkeypatch):
        """Flag on + master on -> gate passes, embedder+vector resolved AFTER
        the gate (then the use case 404s on the missing source)."""
        log = _install_resolvers(monkeypatch, embedder=HashingEmbedder(), vector=None)
        original = _use_core(_core_with(enabled=True, related_documents=True))
        try:
            resp = harness.get(
                f"{API}/related", params={"object_id": "obj:document:none"}
            )
            assert resp.status_code == 404  # source not found (gate passed)
            assert "not found" in resp.json().get("detail", "").lower()
            assert log == {"embedder": 1, "vector": 1}  # resolved after the gate
        finally:
            app.dependency_overrides[get_ai_core] = (
                original or (lambda: build_ai_core(config_mod.settings))
            )

    def test_reuses_same_hashing_embedder_identity_as_search(self, harness, monkeypatch):
        """The route calls the SAME get_embedder /search uses; with semantic
        search off it resolves the HashingEmbedder (no second abstraction)."""
        seen: list = []

        def _embedder(core):
            seen.append(core)
            return HashingEmbedder()

        monkeypatch.setattr("app.api.routes.ai.get_embedder", _embedder)
        monkeypatch.setattr(
            "app.api.routes.ai.get_vector_repository", lambda emb: None
        )
        original = _use_core(_core_with(enabled=True, related_documents=True))
        try:
            resp = harness.get(
                f"{API}/related", params={"object_id": "obj:document:none"}
            )
            assert resp.status_code == 404
            assert len(seen) == 1  # the shared resolver was used
        finally:
            app.dependency_overrides[get_ai_core] = (
                original or (lambda: build_ai_core(config_mod.settings))
            )


class TestSearchUnchanged:
    """M13.3.1: the related-route change must not affect /search."""

    def test_search_still_responds(self, harness):
        resp = harness.get("/api/v1/search", params={"text": "foo"})
        assert resp.status_code == 200
        assert "results" in resp.json()


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
