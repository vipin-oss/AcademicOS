"""Regression tests: health-overclaim fix + streaming enforcement (M11.3.4).

Behavioural proof of the two verified production contract defects:
- health never reports 'ok' for an unverified provider (strongest claim is 'configured');
- streaming configuration (global AI_STREAMING_ENABLED + per-provider streaming_enabled)
  is enforced — stream() raises when disabled; generate() is unaffected.
"""
from __future__ import annotations

import httpx
import pytest

from app.application.dtos.ai import GenerationPrompt, ProviderConfig
from app.infrastructure.ai.llm.openai import LlmProviderError, OpenAIProvider


def _cfg(**over) -> ProviderConfig:
    base = dict(provider_id="oa", kind="openai", model="gpt-4o-mini",
                base_url="http://llm.example/v1", streaming_enabled=True)
    base.update(over)
    return ProviderConfig(**base)


def _ok_handler(content="answer"):
    return lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class TestHealthNeverOverclaims:
    def test_executable_provider_reports_configured_not_ok(self):
        """A provider with base_url (executable) → aggregate status 'configured',
        NOT 'ok' — the system does not claim verified reachability."""
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        gw = _cfg(base_url="http://x/v1")
        # OpenAIProvider needs to report executable=True for this provider.
        provider = OpenAIProvider(gw)
        core = AiCore(
            registry=ProviderRegistry(), gateways={"oa": provider},
            config=AiConfigView(enabled=True, default_provider="oa", default_model="",
                                 temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                                 streaming_enabled=True,
                                 feature_flags={"chat": False, "rag": False, "memory": False,
                                                "agents": False, "document_understanding": False,
                                                "streaming": True}),
            default_provider="oa",
        )
        assert core.health_summary().status == "configured"

    def test_non_executable_provider_never_configured(self):
        """A provider without base_url → status 'not_configured'."""
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        provider = OpenAIProvider(_cfg(base_url=""))  # declared, not executable
        core = AiCore(
            registry=ProviderRegistry(), gateways={"oa": provider},
            config=AiConfigView(enabled=True, default_provider="oa", default_model="",
                                 temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                                 streaming_enabled=True,
                                 feature_flags={"chat": False, "rag": False, "memory": False,
                                                "agents": False, "document_understanding": False,
                                                "streaming": True}),
            default_provider="oa",
        )
        assert core.health_summary().status == "not_configured"


class TestStreamingEnforcement:
    def test_streaming_disabled_raises(self):
        """ProviderConfig.streaming_enabled=False → stream() raises immediately."""
        client = httpx.Client(transport=httpx.MockTransport(_ok_handler()))
        gw = OpenAIProvider(_cfg(streaming_enabled=False), client=client)
        with pytest.raises(LlmProviderError, match="disabled"):
            gw.stream(GenerationPrompt(user="hi"))

    def test_streaming_enabled_works(self):
        """ProviderConfig.streaming_enabled=True → stream() succeeds."""
        client = httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=(
                b'data: {"choices": [{"delta": {"content": "Hi"}}]}\n\n'
                b'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n'
                b'data: [DONE]\n\n'
            ))
        ))
        gw = OpenAIProvider(_cfg(streaming_enabled=True), client=client)
        events = list(gw.stream(GenerationPrompt(user="hi")))
        assert any(e.kind == "token" for e in events)

    def test_sync_generate_unaffected_by_streaming_disabled(self):
        """generate() works regardless of streaming_enabled."""
        client = httpx.Client(transport=httpx.MockTransport(_ok_handler("sync ok")))
        gw = OpenAIProvider(_cfg(streaming_enabled=False), client=client)
        result = gw.generate(GenerationPrompt(user="hi"))
        assert result.text == "sync ok"

    def test_global_streaming_off_disables_all_providers(self):
        """build_ai_core with AI_STREAMING_ENABLED=False → all providers get
        streaming_enabled=False."""
        from app.infrastructure.ai.provider_factory import build_ai_core

        class _Settings:
            ai_enabled = True
            ai_default_provider = "oa"
            ai_default_model = ""
            ai_temperature = 0.0
            ai_max_tokens = 2048
            ai_timeout_seconds = 30.0
            ai_streaming_enabled = False  # GLOBAL OFF
            ai_chat_enabled = False
            ai_rag_enabled = False
            ai_memory_enabled = False
            ai_agents_enabled = False
            ai_document_understanding_enabled = False
            ai_providers_json = (
                '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
                ' "base_url": "http://x/v1", "streaming_enabled": true}]'
            )
            assistant_default_model = ""
            assistant_models_json = ""
            assistant_llm_base_url = None
            assistant_llm_model = ""
            assistant_llm_api_key = ""
            assistant_llm_timeout_seconds = 30.0

        core = build_ai_core(_Settings())
        gw = core.gateway("oa")
        # The per-provider streaming was True, but global is False → enforced off.
        assert gw._config.streaming_enabled is False
