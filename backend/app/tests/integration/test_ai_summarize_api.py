"""Integration tests: POST /ai/summarize (Sprint M12.1).

Tests the HTTP contract: feature-flag enforcement, authentication gate,
error mapping (404, 403, 422). The full generation path is covered by the
unit tests (test_summarize_document.py).
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
from app.infrastructure.db.models.object_model import Base
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
        object_type=ObjectType.USER, title="sum.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:sum-test-0001"),
    )
    from app.infrastructure.db.models.object_model import ObjectModel
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="sum.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    # A real AiCore with no providers (gateway() raises → honest fallback).
    app.dependency_overrides[get_ai_core] = lambda: build_ai_core(config_mod.settings)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


class TestFeatureFlagAndAuth:
    def test_summarize_404_when_flag_off(self, harness):
        original = config_mod.settings.ai_summarization_enabled
        config_mod.settings.ai_summarization_enabled = False
        try:
            resp = harness.post(f"{API}/summarize", json={"object_id": "x"})
            assert resp.status_code == 404
        finally:
            config_mod.settings.ai_summarization_enabled = original

    def test_summarize_requires_auth(self, harness):
        original = config_mod.settings.ai_summarization_enabled
        config_mod.settings.ai_summarization_enabled = True
        try:
            app.dependency_overrides.pop(get_current_user, None)
            resp = harness.post(f"{API}/summarize", json={"object_id": "x"})
            assert resp.status_code == 401
        finally:
            config_mod.settings.ai_summarization_enabled = original


class TestErrorMapping:
    def test_unknown_document_404(self, harness):
        original = config_mod.settings.ai_summarization_enabled
        config_mod.settings.ai_summarization_enabled = True
        try:
            resp = harness.post(
                f"{API}/summarize",
                json={"object_id": str(ObjectId.generate(ObjectType.DOCUMENT))},
            )
            assert resp.status_code == 404
        finally:
            config_mod.settings.ai_summarization_enabled = original

    def test_missing_object_id_field_422(self, harness):
        original = config_mod.settings.ai_summarization_enabled
        config_mod.settings.ai_summarization_enabled = True
        try:
            resp = harness.post(f"{API}/summarize", json={})
            assert resp.status_code == 422  # pydantic extra=forbid + missing field
        finally:
            config_mod.settings.ai_summarization_enabled = original
