"""Integration tests: POST /ai/chat and /ai/chat/stream (Sprint M15 — F17).

Tests the HTTP contract: feature-flag enforcement, authentication gate,
AI-master-switch authority (no embedding/gateway touch when disabled), error
mapping (404 / 422), and that the enabled path proceeds. The full
generation pipeline is covered by the unit tests (test_chat.py).
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
        ObjectType.USER, "chat.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:chat-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="chat.test",
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
                "chat": flags.get("chat", False),
                "rag": False, "memory": False,
                "agents": False, "document_understanding": False,
                "streaming": True, "summarization": False,
                "semantic_search": False, "qa": False,
                "enrichment": False, "related_documents": False,
            },
        ),
    )


class TestFeatureFlagAndAuth:
    def test_chat_404_when_flag_off(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=False)
        resp = harness.post(f"{API}/chat", json={"message": "hi"})
        assert resp.status_code == 404

    def test_chat_requires_auth(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = harness.post(f"{API}/chat", json={"message": "hi"})
            assert resp.status_code == 401
        finally:
            app.dependency_overrides[get_current_user] = lambda: UniversalObject.create(
                ObjectType.USER, "chat.test", created_by="system",
                status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:chat-test-0001"),
            )

    def test_master_switch_off_blocks_even_when_flag_on(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=False, chat=True)
        resp = harness.post(f"{API}/chat", json={"message": "hi"})
        assert resp.status_code == 404


class TestRequestValidation:
    def test_missing_message_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={})
        assert resp.status_code == 422

    def test_unknown_field_422(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={"message": "hi", "bogus": 1})
        assert resp.status_code == 422

    def test_history_accepts_empty(self, harness):
        """An empty history list is valid (first turn of a chat)."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={"message": "hi", "history": []})
        # Enabled + no real gateway → honest fallback answer (available=False), 200.
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    def test_history_with_turns_accepted(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={
            "message": "and then?",
            "history": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        })
        assert resp.status_code == 200


class TestStreamingEndpoint:
    def test_stream_404_when_flag_off(self, harness):
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=False)
        resp = harness.post(f"{API}/chat/stream", json={"message": "hi"})
        assert resp.status_code == 404


class TestConversationPersistence:
    """M19 — server-side conversation persistence for chat."""

    def test_first_turn_creates_conversation(self, harness):
        """No conversation_id + no history → a new conversation is created
        and its id is returned."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={"message": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["conversation_id"] is not None
        assert body["conversation_id"].startswith("obj:ai_conversation:")

    def test_second_turn_continues_conversation(self, harness):
        """Sending the conversation_id from the first turn loads its history."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        first = harness.post(f"{API}/chat", json={"message": "hello"})
        conv_id = first.json()["conversation_id"]
        assert conv_id is not None

        second = harness.post(
            f"{API}/chat", json={"message": "follow up", "conversation_id": conv_id},
        )
        assert second.status_code == 200
        assert second.json()["conversation_id"] == conv_id  # same conversation

    def test_client_history_mode_no_persistence(self, harness):
        """conversation_id absent + history present → M15 stateless mode
        (no conversation_id in the response)."""
        app.dependency_overrides[get_ai_core] = lambda: _core_with(enabled=True, chat=True)
        resp = harness.post(f"{API}/chat", json={
            "message": "hi",
            "history": [{"role": "user", "content": "previous"}],
        })
        assert resp.status_code == 200
        assert resp.json()["conversation_id"] is None
