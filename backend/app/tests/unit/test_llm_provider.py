"""Unit tests for the production LLM provider transport (Sprint-6 M2 P2).

Pure transport behind the AssistantProvider port: deterministic request
construction, bounded retries on transient failures only, graceful errors
(fallback boundary consumes them), timeout support. httpx.MockTransport
fakes the wire — no network in CI.
"""
from __future__ import annotations

import json

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
    assert body["citations"] == []  # no evidence -> no citations on the wire
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


def test_chain_falls_back_on_5xx_after_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={})

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="fallback", sources=["rules"],
            )

    chain = FallbackAssistantProvider(
        _provider(handler, retry_attempts=2, retry_backoff_seconds=0), Fallback()
    )
    out = chain.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 2  # bounded retries were spent
    assert out.summary == "fallback"  # then the deterministic fallback answered


def test_chain_falls_back_on_timeout():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("timed out", request=request)

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="fallback", sources=["rules"],
            )

    chain = FallbackAssistantProvider(
        _provider(handler, retry_attempts=2, retry_backoff_seconds=0), Fallback()
    )
    out = chain.answer("q", "u:1", prompt=_prompt())
    assert calls["n"] == 2
    assert out.summary == "fallback"  # timeout never crashes the assistant


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


# ------------------------------------------------------------- streaming (M4)


def _sse_content(*chunks: str) -> bytes:
    """OpenAI-style SSE body: one data line per chunk, then [DONE]."""
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks]
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


def _stream_prompt() -> AssistantPrompt:
    return AssistantPrompt(
        system="sys",
        user="RETRIEVED CONTEXT:\n- [1] [document] Paper\n\nQUESTION: find quantum",
        citations=(),
    )


def test_stream_yields_tokens_then_completion():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse_content("Hello", " world", "!"))

    provider = _provider(handler)
    events = list(provider.stream("find quantum", "u:1", prompt=_stream_prompt()))

    tokens = [e for e in events if e["type"] == "token"]
    assert [t["delta"] for t in tokens] == ["Hello", " world", "!"]
    completes = [e for e in events if e["type"] == "complete"]
    assert len(completes) == 1
    answer = completes[0]["answer"]
    assert answer.summary == "Hello world!"
    assert answer.intent == "llm"
    assert answer.metrics["model"] == "test-model"
    # The request carried stream=True and the citations.
    assert captured["body"]["stream"] is True
    assert captured["body"]["citations"] == []


def test_stream_4xx_fails_immediately_no_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={})

    provider = _provider(handler)
    with pytest.raises(LlmProviderError, match="401"):
        list(provider.stream("q", "u:1", prompt=_stream_prompt()))
    assert calls["n"] == 1


def test_stream_connect_error_retries_then_raises():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler, retry_attempts=3, retry_backoff_seconds=0)
    with pytest.raises(LlmProviderError, match="unreachable"):
        list(provider.stream("q", "u:1", prompt=_stream_prompt()))
    assert calls["n"] == 3


def test_stream_5xx_retries_before_first_token():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={})

    provider = _provider(handler, retry_attempts=2, retry_backoff_seconds=0)
    with pytest.raises(LlmProviderError, match="503"):
        list(provider.stream("q", "u:1", prompt=_stream_prompt()))
    assert calls["n"] == 2


def test_stream_malformed_chunk_raises_after_tokens():
    """A malformed SSE chunk after valid tokens raises immediately — the
    tokens already yielded stand, and the error propagates (the chain
    converts it into a deterministic fallback completion)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'data: {"choices": [{"delta": {"content": "a"}}]}\n\n'
            b'data: bad\n\ndata: [DONE]\n\n',
        )

    provider = _provider(handler)
    gen = provider.stream("q", "u:1", prompt=_stream_prompt())
    assert next(gen)["delta"] == "a"
    with pytest.raises(LlmProviderError, match="unexpected shape"):
        next(gen)


def test_stream_empty_text_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse_content())

    provider = _provider(handler)
    with pytest.raises(LlmProviderError, match="no text"):
        list(provider.stream("q", "u:1", prompt=_stream_prompt()))


def test_chain_stream_passes_tokens_through():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse_content("token", "s"))

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            raise AssertionError("fallback must not run on success")

    chain = FallbackAssistantProvider(
        _provider(handler), Fallback()
    )
    events = list(chain.stream("q", "u:1", prompt=_stream_prompt()))
    assert [e["type"] for e in events] == ["token", "token", "complete"]
    assert events[-1]["answer"].summary == "tokens"


def test_chain_stream_falls_back_on_primary_failure():
    class BoomStream:
        name = "boom"

        def stream(self, question, asked_by, *, context=None, prompt=None):
            yield {"type": "token", "delta": "partial"}
            raise LlmProviderError("connection lost mid-stream")

    class Fallback:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="fallback answer", sources=["rules"],
            )

    chain = FallbackAssistantProvider(BoomStream(), Fallback())
    events = list(chain.stream("q", "u:1", prompt=_stream_prompt()))
    assert [e["type"] for e in events] == ["token", "complete"]
    assert events[0]["delta"] == "partial"  # tokens already sent
    assert events[1]["answer"].summary == "fallback answer"  # then degraded


def test_chain_stream_without_primary_stream_yields_single_completion():
    class NoStream:
        name = "rules-v1"

        def answer(self, question, asked_by, *, context=None, prompt=None):
            return AssistantAnswerOutput(
                intent="knowledge_search", intent_label="Knowledge search",
                question=question, summary="deterministic", sources=["rules"],
            )

    chain = FallbackAssistantProvider(NoStream(), NoStream())
    events = list(chain.stream("q", "u:1"))
    assert len(events) == 1
    assert events[0]["type"] == "complete"
    assert events[0]["answer"].summary == "deterministic"


def test_stream_cancellation_closes_without_events():
    """Closing the iterator mid-stream (client disconnect) must not yield a
    completion and must propagate GeneratorExit."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse_content("a", "b", "c"))

    provider = _provider(handler)
    gen = provider.stream("q", "u:1", prompt=_stream_prompt())
    assert next(gen)["delta"] == "a"
    gen.close()  # client disconnect: generator closed mid-stream
    with pytest.raises(StopIteration):
        next(gen)  # no further events, no completion
