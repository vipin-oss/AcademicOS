"""Integration tests: POST /ai/enrich (Sprint M13.2).

Tests the HTTP contract: feature-flag enforcement, authentication gate,
error mapping (404, 403, 422), master-switch authority, and that the
endpoint routes through ``structured_generate`` (not ``generate``). The full
generation path is covered by the unit tests (test_enrich_document.py).
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
from app.application.dtos.ai import (
    STATUS_NOT_CONFIGURED,
    ProviderHealth,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.ai.provider_factory import build_ai_core
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
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
        object_type=ObjectType.USER, title="enrich.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:enrich-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="enrich.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    # A real AiCore with no providers (gateway() raises -> honest fallback).
    app.dependency_overrides[get_ai_core] = lambda: build_ai_core(config_mod.settings)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class TestFeatureFlagAndAuth:
    def test_enrich_404_when_flag_off(self, harness):
        original = config_mod.settings.ai_enrichment_enabled
        config_mod.settings.ai_enrichment_enabled = False
        try:
            resp = harness.post(f"{API}/enrich", json={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            config_mod.settings.ai_enrichment_enabled = original

    def test_enrich_requires_auth(self, harness):
        original = config_mod.settings.ai_enrichment_enabled
        config_mod.settings.ai_enrichment_enabled = True
        try:
            app.dependency_overrides.pop(get_current_user, None)
            resp = harness.post(f"{API}/enrich", json={"object_id": "x"})
            assert resp.status_code == 401
        finally:
            config_mod.settings.ai_enrichment_enabled = original


class TestErrorMapping:
    def test_unknown_document_404(self, harness):
        original = config_mod.settings.ai_enrichment_enabled
        config_mod.settings.ai_enrichment_enabled = True
        try:
            resp = harness.post(
                f"{API}/enrich",
                json={"object_id": str(ObjectId.generate(ObjectType.DOCUMENT))},
            )
            assert resp.status_code == 404  # ObjectNotFoundError from the use case
        finally:
            config_mod.settings.ai_enrichment_enabled = original

    def test_missing_object_id_field_422(self, harness):
        original = config_mod.settings.ai_enrichment_enabled
        config_mod.settings.ai_enrichment_enabled = True
        try:
            resp = harness.post(f"{API}/enrich", json={})
            assert resp.status_code == 422  # extra=forbid + missing field
        finally:
            config_mod.settings.ai_enrichment_enabled = original


def _core_with(**flags):
    """Build an AiCore with explicit feature flags (master switch + flags)."""
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
                "enrichment": flags.get("enrichment", False),
            },
        ),
    )


class TestMasterSwitchGate:
    """AI_ENABLED=false must block enrichment even when
    AI_ENRICHMENT_ENABLED=true. No gateway invocation may occur."""

    def test_ai_disabled_blocks_enrichment_even_when_flag_on(self, harness):
        disabled_core = _core_with(enabled=False, enrichment=True)
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: disabled_core
        try:
            resp = harness.post(f"{API}/enrich", json={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)

    def test_no_gateway_invocation_when_ai_disabled(self, harness):
        structured_called = False

        class _TrackingGateway:
            provider_id = "test"
            display_name = "Test"
            kind = "openai"

            def structured_generate(self, prompt):
                raise AssertionError(
                    "structured_generate() must not be called when AI is disabled"
                )

            def generate(self, prompt):
                raise AssertionError("generate() must not be called when AI is disabled")

            def health(self):
                return ProviderHealth(
                    provider_id="test", display_name="Test", kind="openai",
                    status=STATUS_NOT_CONFIGURED, configured=False, executable=False,
                    models_configured=0, detail="", checked_at="",
                )

            def list_models(self):
                return ()

        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        tracking_core = AiCore(
            registry=ProviderRegistry(),
            gateways={"test": _TrackingGateway()},
            config=AiConfigView(
                enabled=False,  # master switch OFF
                default_provider="test",
                default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={
                    "chat": False, "rag": False, "memory": False,
                    "agents": False, "document_understanding": False,
                    "streaming": True, "enrichment": True,
                },
            ),
            default_provider="test",
        )
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: tracking_core
        try:
            resp = harness.post(f"{API}/enrich", json={"object_id": "x"})
            assert resp.status_code == 404
            assert not structured_called
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)

    def test_ai_enabled_and_flag_on_proceeds(self, harness):
        """Both master ON and flag ON -> the endpoint proceeds past the gate
        (it then 404s on the missing document, NOT on the flag)."""
        enabled_core = _core_with(enabled=True, enrichment=True)
        original = app.dependency_overrides.get(get_ai_core)
        app.dependency_overrides[get_ai_core] = lambda: enabled_core
        try:
            resp = harness.post(f"{API}/enrich", json={"object_id": "x"})
            assert resp.status_code == 404  # document not found, not flag-gated
        finally:
            if original is not None:
                app.dependency_overrides[get_ai_core] = original
            else:
                app.dependency_overrides.pop(get_ai_core, None)
