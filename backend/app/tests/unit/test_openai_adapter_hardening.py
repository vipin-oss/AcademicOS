"""Unit tests: OpenAI adapter production hardening (Sprint M11.3).

Covers the M11.3 hardening of ``OpenAIProvider``: generation policy in the
request body (max_tokens / temperature), honest finish_reason + token-usage
accounting, latency measurement, JSON-mode structured output (a REAL
capability, not faked), httpx client lifecycle / reuse, and accurate
capability reporting. httpx.MockTransport fakes the wire — no network.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.application.dtos.ai import (
    GenerationPrompt,
    ProviderConfig,
    StructuredGenerationPrompt,
)
from app.infrastructure.ai.llm.openai import LlmProviderError, OpenAIProvider


def _cfg(**over) -> ProviderConfig:
    base = dict(provider_id="oa", kind="openai", model="gpt-4o-mini",
                base_url="http://llm.example/v1", api_key="k", timeout_seconds=30.0,
                max_tokens=128, temperature=0.0)
    base.update(over)
    return ProviderConfig(**base)


def _provider(handler, *, config=None, **kw) -> OpenAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAIProvider(config or _cfg(), client=client, **kw)


def _ok(content="answer", *, finish="stop", usage=None) -> dict:
    msg = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
    if usage is not None:
        msg["usage"] = usage
    return msg


class TestRequestBodyPolicy:
    def test_body_carries_config_max_tokens_and_temperature(self):
        captured = {}

        def h(req):
            captured["body"] = json.loads(req.content)
            return httpx.Response(200, json=_ok())

        _provider(h).generate(GenerationPrompt(user="hi"))
        assert captured["body"]["max_tokens"] == 128
        assert captured["body"]["temperature"] == 0
        assert captured["body"]["model"] == "gpt-4o-mini"

    def test_prompt_overrides_temperature_and_max_tokens(self):
        captured = {}

        def h(req):
            captured["body"] = json.loads(req.content)
            return httpx.Response(200, json=_ok())

        _provider(h).generate(
            GenerationPrompt(user="hi", temperature=0.7, max_tokens=16)
        )
        assert captured["body"]["temperature"] == 0.7
        assert captured["body"]["max_tokens"] == 16


class TestAccounting:
    def test_finish_reason_and_usage_parsed_when_present(self):
        def h(req):
            return httpx.Response(200, json=_ok("x", finish="length",
                                                usage={"prompt_tokens": 7, "completion_tokens": 3}))

        res = _provider(h).generate(GenerationPrompt(user="hi"))
        assert res.finish_reason == "length"
        assert res.usage.estimated is False
        assert res.usage.input_tokens == 7
        assert res.usage.output_tokens == 3

    def test_usage_estimated_when_endpoint_reports_none(self):
        _provider(lambda r: httpx.Response(200, json=_ok("x"))).generate(
            GenerationPrompt(user="hi")
        ).usage.estimated is True

    def test_latency_measured(self):
        res = _provider(lambda r: httpx.Response(200, json=_ok("x"))).generate(
            GenerationPrompt(user="hi")
        )
        assert isinstance(res.latency_ms, int) and res.latency_ms >= 0


class TestStructuredOutput:
    def test_structured_returns_parsed_json(self):
        def h(req):
            body = json.loads(req.content)
            assert body["response_format"] == {"type": "json_object"}
            return httpx.Response(200, json=_ok(json.dumps({"answer": 42})))

        res = _provider(h).structured_generate(
            StructuredGenerationPrompt(user="extract", schema={"type": "object"})
        )
        assert res.value == {"answer": 42}
        assert res.raw_text

    def test_structured_rejects_non_object_json(self):
        p = _provider(lambda r: httpx.Response(200, json=_ok("[1, 2, 3]")))
        with pytest.raises(LlmProviderError, match="not a JSON object"):
            p.structured_generate(StructuredGenerationPrompt(user="x", schema={"type": "object"}))

    def test_structured_rejects_invalid_json(self):
        p = _provider(lambda r: httpx.Response(200, json=_ok("not json at all")))
        with pytest.raises(LlmProviderError, match="not valid JSON"):
            p.structured_generate(StructuredGenerationPrompt(user="x", schema={"type": "object"}))


class TestStreamAccounting:
    def _sse(self, *chunks, finish=None, usage=None) -> bytes:
        lines = []
        for c in chunks:
            lines.append(f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}")
        last = {"choices": [{"delta": {}, "finish_reason": finish or "stop"}]}
        if usage is not None:
            last["usage"] = usage
        lines.append(f"data: {json.dumps(last)}")
        lines.append("data: [DONE]")
        return ("\n\n".join(lines) + "\n\n").encode()

    def test_stream_parses_terminal_usage_and_finish(self):
        p = _provider(
            lambda r: httpx.Response(200, content=self._sse(
                "Hel", "lo", finish="length", usage={"prompt_tokens": 2, "completion_tokens": 2}
            ))
        )
        events = list(p.stream(GenerationPrompt(user="hi")))
        complete = [e for e in events if e.kind == "complete"][0]
        assert complete.result.finish_reason == "length"
        assert complete.result.usage.estimated is False
        assert complete.result.usage.output_tokens == 2

    def test_stream_body_requests_usage_inclusion(self):
        captured = {}

        def h(r):
            captured["body"] = json.loads(r.content)
            return httpx.Response(200, content=self._sse("a"))

        _provider(h).stream(GenerationPrompt(user="hi"))
        # nothing consumed yet (generator not iterated) -> capture on iterate
        # build/iterate explicitly:
        captured.clear()

        def h2(r):
            captured["body"] = json.loads(r.content)
            return httpx.Response(200, content=self._sse("a"))

        list(_provider(h2).stream(GenerationPrompt(user="hi")))
        assert captured["body"]["stream_options"] == {"include_usage": True}


class TestClientLifecycle:
    def test_owned_client_reused_across_calls(self):
        p = OpenAIProvider(_cfg())  # no injected client -> builds its own
        p._client_or_build()
        first = p._owned_client
        p._client_or_build()
        assert p._owned_client is first  # reused, not rebuilt
        p.close()
        assert p._owned_client is None
        p.close()  # idempotent

    def test_injected_client_not_closed(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_ok())))
        p = OpenAIProvider(_cfg(), client=client)
        p.close()  # must not close the injected client
        # The injected client is still usable:
        assert p._client_or_build() is client


class TestCapabilityReporting:
    def test_capabilities_are_real_only(self):
        caps = OpenAIProvider().capabilities
        assert "chat" in caps and "stream" in caps and "structured_output" in caps
        assert "tools" not in caps  # function-calling is NOT implemented


class TestLocalFreeProvider:
    """M16.1 — the core must work with a LOCAL / FREE model and no paid key."""

    def test_generates_without_api_key_and_no_auth_header(self):
        """A local OpenAI-compatible server (Ollama, vLLM, LM Studio) needs no
        API key. The gateway must generate with ``api_key=''`` and send NO
        ``Authorization`` header (local endpoints reject/ignore it)."""
        captured: dict = {}

        def h(req):
            captured["auth"] = req.headers.get("authorization")
            captured["body"] = json.loads(req.content)
            return httpx.Response(200, json=_ok("local-reply"))

        p = _provider(
            h, config=_cfg(api_key="", base_url="http://localhost:11434/v1"),
        )
        res = p.generate(GenerationPrompt(user="hi"))

        assert res.text == "local-reply"
        assert captured["auth"] is None  # no Authorization header for local/free
        assert captured["body"]["model"] == "gpt-4o-mini"  # request well-formed

    def test_structured_generate_works_without_api_key(self):
        """Structured generation (enrichment) also works on a local/free model."""
        def h(req):
            return httpx.Response(200, json=_ok(json.dumps({"title": "T", "summary": "S",
                                                            "tags": [], "categories": [], "keywords": []})))
        p = _provider(h, config=_cfg(api_key="", base_url="http://localhost:11434/v1"))
        res = p.structured_generate(
            StructuredGenerationPrompt(user="extract", schema={"type": "object"})
        )
        assert res.value["title"] == "T"


# ---------------------------------------------------------------------------
# V3 AI fix: Ollama-native streaming/response shape parsing
# ---------------------------------------------------------------------------


def test_extract_delta_handles_ollama_native_streaming():
    """Ollama's /v1/chat/completions streaming emits top-level message.content
    + done flag (no choices[]). The adapter must extract content from it."""
    import json as _json

    from app.infrastructure.ai.llm.openai import OpenAIProvider

    chunk = _json.dumps({
        "model": "qwen2.5:1.5b",
        "message": {"role": "assistant", "content": "AcademicOS AI OK"},
        "done": False,
    })
    delta, finish, _usage = OpenAIProvider._extract_delta(chunk)
    assert delta == "AcademicOS AI OK"
    assert finish is None

    final = _json.dumps({
        "model": "qwen2.5:1.5b",
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
    })
    delta2, finish2, _ = OpenAIProvider._extract_delta(final)
    assert delta2 == ""
    assert finish2 == "stop"


def test_extract_delta_still_handles_openai_standard():
    import json as _json

    from app.infrastructure.ai.llm.openai import OpenAIProvider

    chunk = _json.dumps({"choices": [{"delta": {"content": "Hi"}, "finish_reason": None}]})
    delta, finish, _ = OpenAIProvider._extract_delta(chunk)
    assert delta == "Hi"
    assert finish is None


def test_parse_response_falls_back_to_ollama_native_nonstream():
    """A non-streaming response in Ollama's native shape is parsed, not rejected."""
    import httpx

    from app.infrastructure.ai.llm.openai import OpenAIProvider

    response = httpx.Response(
        200,
        json={"model": "qwen2.5:1.5b", "message": {"role": "assistant", "content": "OK"},
              "done": True, "done_reason": "stop"},
    )
    raw = OpenAIProvider._parse_response(response)
    assert raw.text == "OK"
    assert raw.finish_reason == "stop"
