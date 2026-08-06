"""Unit tests for the production LLM provider transport (Sprint-6 M2 P2).

Pure transport behind the AssistantProvider port: deterministic request
construction, bounded retries on transient failures only, graceful errors
(fallback boundary consumes them), timeout support. httpx.MockTransport
fakes the wire — no network in CI.
"""
from __future__ import annotations

import httpx
import pytest

from app.application.assistant.providers import FallbackAssistantProvider
from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantPrompt,
)
from app.infrastructure.llm.llm_provider import LlmAssistantProvider, LlmProviderError


def _prompt() -> AssistantPrompt:
    return AssistantPrompt(
        system="You are AcademicOS Assistant. Ground your answer in the context.",
        user="RETRIEVED CONTEXT:\n- [document] Quantum Paper (id=obj:document:A)\n\nQUESTION: find quantum",
    )


def _provider(handler, **kwargs) -> LlmAssistantProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LlmAssistantProvider(
        client, model="test-model", base_url="http://llm.example", **kwargs
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": "Quantum mechanics studies nature at small scales."}}]},
    )


def test_request_construction_is_deterministic():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["json"] = _json.loads(request.content)
        return _ok_handler(request)

    provider = _provider(handler)
    out = provider.answer("find quantum", "u:1", prompt=_prompt())

    assert captured["method"] == "POST"
    assert captured["url"] == "http://llm.example/chat/completions"
    body = captured["json"]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0  # deterministic sampling
    assert body["messages"] == [
        {"role": "system", "content": _prompt().system},
        {"role": "user", "content": _prompt().user},
    ]
    assert out.summary == "Quantum mechanics studies nature at small scales."
    assert out.intent == "llm"
    assert out.sources == ["llm"]
    assert out.metrics["model"] == "test-model"


def test_success_parses_answer_output():
    provider = _provider(_ok_handler)
    out = provider.answer("find quantum", "u:1", prompt=_prompt())
    assert isinstance(out, AssistantAnswerOutput)
    assert out.question == "find quantum"
    assert out.summary
    assert out.metrics["provider"] == "llm-v1"


def test_missing_prompt_raises_without_network():
    provider = _provider(_ok_handler)
    with pytest.raises(LlmProviderError, match="No prompt"):
        provider.answer("find quantum", "u:1")


def test_4xx_fails_immediately_no_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "bad key"})

    provider = _provider(handler)
    with pytest.raises(LlmProviderError, match="401"):
        provider.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 1  # no retry on client errors


def test_5xx_retries_then_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={})

    provider = _provider(handler, retry_attempts=3, retry_backoff_seconds=0)
    with pytest.raises(LlmProviderError, match="503"):
        provider.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 3  # bounded retries


def test_timeout_retries_then_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("connection timed out", request=request)

    provider = _provider(handler, retry_attempts=3, retry_backoff_seconds=0)
    with pytest.raises(LlmProviderError, match="unreachable"):
        provider.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 3


def test_transient_then_success_recovers():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("connection refused", request=request)
        return _ok_handler(request)

    provider = _provider(handler, retry_attempts=3, retry_backoff_seconds=0)
    out = provider.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 3
    assert "Quantum mechanics" in out.summary


def test_malformed_response_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    provider = _provider(handler)
    with pytest.raises(LlmProviderError, match="unexpected shape"):
        provider.answer("q", "u:1", prompt=_prompt())


def test_empty_content_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    provider = _provider(handler)
    with pytest.raises(LlmProviderError, match="no text"):
        provider.answer("q", "u:1", prompt=_prompt())


def test_fallback_chain_answers_on_primary_failure():
    class BoomProvider:
        name = "boom"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            raise LlmProviderError("endpoint down")

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="deterministic fallback", sources=["rules"],
            )

    chain = FallbackAssistantProvider(BoomProvider(), Fallback())
    out = chain.answer("q", "u:1", prompt=_prompt())
    assert out.summary == "deterministic fallback"  # assistant stays operational


def test_fallback_chain_passes_through_success():
    calls = {"n": 0}

    class Primary:
        name = "llm-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            nonlocal calls
            calls["n"] += 1
            return AssistantAnswerOutput(
                intent="llm", intent_label="Assistant", question=question,
                summary=f"llm:{question}", sources=["llm"],
            )

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            raise AssertionError("fallback must not run on success")

    chain = FallbackAssistantProvider(Primary(), Fallback())
    out = chain.answer("q", "u:1")
    assert out.summary == "llm:q"
    assert calls["n"] == 1
