"""Unit tests: AI configuration view (Sprint M11.1)."""
from __future__ import annotations

from app.application.ai.config import AiConfigView


class _StubSettings:
    """Minimal settings stand-in (the view only reads AI fields)."""

    ai_enabled = True
    ai_default_provider = "local"
    ai_default_model = ""
    ai_temperature = 0.0
    ai_max_tokens = 2048
    ai_timeout_seconds = 30.0
    ai_streaming_enabled = True
    ai_chat_enabled = False
    ai_summarization_enabled = False
    ai_semantic_search_enabled = False
    ai_qa_enabled = False
    ai_enrichment_enabled = False
    ai_related_documents_enabled = False
    ai_rag_enabled = False
    ai_memory_enabled = False
    ai_agents_enabled = False
    ai_document_understanding_enabled = False


class TestAiConfigView:
    def test_from_settings_defaults(self):
        view = AiConfigView.from_settings(_StubSettings())
        assert view.enabled is True
        assert view.default_provider == "local"
        assert view.default_model == ""
        assert view.temperature == 0.0
        assert view.max_tokens == 2048
        assert view.timeout_seconds == 30.0
        assert view.default_provider_valid is True

    def test_feature_flags_all_present_and_off_by_default(self):
        view = AiConfigView.from_settings(_StubSettings())
        assert view.feature_flags == {
            "chat": False,
            "rag": False,
            "memory": False,
            "agents": False,
            "document_understanding": False,
            "streaming": True,
            "summarization": False,
            "semantic_search": False,
            "qa": False,
            "enrichment": False,
            "related_documents": False,
        }

    def test_custom_values_projected(self):
        class Custom(_StubSettings):
            ai_enabled = False
            ai_default_provider = "openai"
            ai_default_model = "gpt-4o-mini"
            ai_temperature = 0.7
            ai_max_tokens = 1024
            ai_timeout_seconds = 15.0
            ai_streaming_enabled = False
            ai_chat_enabled = True

        view = AiConfigView.from_settings(Custom())
        assert view.enabled is False
        assert view.default_provider == "openai"
        assert view.default_model == "gpt-4o-mini"
        assert view.temperature == 0.7
        assert view.max_tokens == 1024
        assert view.timeout_seconds == 15.0
        assert view.feature_flags["chat"] is True
        assert view.feature_flags["streaming"] is False

    def test_unknown_default_provider_reported_invalid(self):
        class Custom(_StubSettings):
            ai_default_provider = "oepnai"  # typo must not crash startup

        view = AiConfigView.from_settings(Custom())
        assert view.default_provider_valid is False

    def test_empty_default_provider_falls_back_to_local(self):
        class Custom(_StubSettings):
            ai_default_provider = ""

        view = AiConfigView.from_settings(Custom())
        assert view.default_provider == "local"
        assert view.default_provider_valid is True
