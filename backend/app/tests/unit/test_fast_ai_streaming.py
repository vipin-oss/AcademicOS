"""Focused tests: Phase B true streaming + Phase C dynamic output budget +
Phase E model warmth (keep_alive).

- provisional tokens reach the stream BEFORE the completion event;
- the completion is authoritative (full answer, verified citations);
- a failure yields available=False completion (never a fake success);
- per-prompt max_tokens is honoured end-to-end (use case -> GenerationPrompt);
- keep_alive is parsed from AI_PROVIDERS_JSON and passed to the provider body.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from app.application.ai.providers.config import parse_provider_configs
from app.application.dtos.ai import (
    GenerationEvent,
    GenerationPrompt,
    GenerationResult,
    TokenUsage,
)
from app.application.use_cases.ai.grounded_qa import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    GroundedQAUseCase,
)


class _User:
    id = "obj:user:test-0001"

    class _Meta:
        def get_value(self, key):
            return None

    metadata = _Meta()


class _RecordingGateway:
    """Yields scripted events and records the GenerationPrompt it received."""

    provider_id = "test"
    display_name = "test"
    kind = "openai"

    def __init__(self, events, generate_text="full answer"):
        self._events = list(events)
        self._generate_text = generate_text
        self.seen_prompt: GenerationPrompt | None = None

    def stream(self, prompt):
        self.seen_prompt = prompt
        for event in self._events:
            yield event

    def generate(self, prompt):
        self.seen_prompt = prompt
        return GenerationResult(text=self._generate_text, model="test",
                                usage=TokenUsage(estimated=True))

    def health(self):
        from app.application.dtos.ai import ProviderHealth
        return ProviderHealth(provider_id="test", display_name="test", kind="openai",
                              status="configured", configured=True, executable=True,
                              operational=None, detail="")

    def list_models(self):
        return ()

    def close(self):
        pass


class _Retrieval:
    def retrieve(self, *a, **k):
        from app.application.dtos.assistant import AssistantRetrievalResult
        return AssistantRetrievalResult(items=(), search_count=0, graph_count=0)


class _Repo:
    def get_by_id(self, oid):
        return None

    def find_by_ids(self, ids):
        return []


class _Core:
    def __init__(self, gateway):
        self._gateway = gateway

    def gateway(self):
        return self._gateway


def _make_use_case(gateway, *, max_output_tokens=None) -> GroundedQAUseCase:
    return GroundedQAUseCase(
        _Repo(), _Retrieval(), _Core(gateway),
        max_output_tokens=max_output_tokens,
    )


def _user():
    return _User()


# ---------------------------------------------------------------- streaming
def test_first_token_reaches_stream_before_completion():
    gw = _RecordingGateway(
        events=[
            GenerationEvent(kind="token", delta="Hel"),
            GenerationEvent(kind="token", delta="lo"),
            GenerationEvent(kind="complete", result=GenerationResult(
                text="Hello", model="test", usage=TokenUsage(estimated=True))),
        ]
    )
    use_case = _make_use_case(gw)
    events = list(use_case.stream("hi", _user()))

    types = [e["type"] for e in events]
    assert types == ["token", "token", "complete"], (
        "Phase B: provisional tokens must precede the completion event"
    )
    assert [e["delta"] for e in events if e["type"] == "token"] == ["Hel", "lo"]
    completion = events[-1]["result"]
    assert completion.available is True
    assert completion.answer == "Hello"


def test_stream_tokens_are_incremental_not_batched():
    """Each gateway token becomes its own stream event immediately — the
    use case no longer buffers chunks until completion."""
    gw = _RecordingGateway(
        events=[
            GenerationEvent(kind="token", delta="a"),
            GenerationEvent(kind="token", delta="b"),
            GenerationEvent(kind="token", delta="c"),
            GenerationEvent(kind="complete", result=GenerationResult(
                text="abc", model="test", usage=TokenUsage(estimated=True))),
        ]
    )
    events = list(_make_use_case(gw).stream("q", _user()))
    assert [e["delta"] for e in events if e["type"] == "token"] == ["a", "b", "c"]


def test_failed_generation_completion_is_not_a_success():
    gw = _RecordingGateway(
        events=[
            GenerationEvent(kind="token", delta="partial"),
        ]  # no complete event
    )
    events = list(_make_use_case(gw).stream("q", _user()))
    completions = [e for e in events if e["type"] == "complete"]
    assert len(completions) == 1
    assert completions[0]["result"].available is False


# ------------------------------------------------------------ output budget
def test_default_budget_constant_is_512():
    assert DEFAULT_MAX_OUTPUT_TOKENS == 512


def test_max_output_tokens_reaches_generation_prompt():
    gw = _RecordingGateway(events=[GenerationEvent(kind="complete", result=GenerationResult(
        text="x", model="test", usage=TokenUsage(estimated=True)))])
    use_case = _make_use_case(gw, max_output_tokens=512)
    list(use_case.stream("q", _user()))
    assert gw.seen_prompt is not None
    assert gw.seen_prompt.max_tokens == 512


def test_no_budget_keeps_none():
    gw = _RecordingGateway(events=[GenerationEvent(kind="complete", result=GenerationResult(
        text="x", model="test", usage=TokenUsage(estimated=True)))])
    use_case = _make_use_case(gw, max_output_tokens=None)
    list(use_case.stream("q", _user()))
    assert gw.seen_prompt.max_tokens is None  # provider config default


def test_sync_generate_also_respects_budget():
    gw = _RecordingGateway(events=[])
    use_case = _make_use_case(gw, max_output_tokens=512)
    use_case.execute("q", _user())
    assert gw.seen_prompt is not None
    assert gw.seen_prompt.max_tokens == 512


# ------------------------------------------------------------ model warmth
def test_keep_alive_parsed_from_provider_json():
    configs = parse_provider_configs(
        '[{"provider_id":"local-ollama","kind":"openai","model":"llama3.2",'
        '"base_url":"http://localhost:11434/v1","api_key":"",'
        '"max_tokens":512,"streaming_enabled":true,"timeout_seconds":120,'
        '"keep_alive":"30m"}]'
    )
    assert configs[0].keep_alive == "30m"
    assert configs[0].max_tokens == 512


def test_keep_alive_absent_is_none():
    configs = parse_provider_configs(
        '[{"provider_id":"p","kind":"openai","model":"m","base_url":"http://x/v1"}]'
    )
    assert configs[0].keep_alive is None


def test_keep_alive_included_in_request_body():
    from app.infrastructure.ai.llm.openai import OpenAIProvider
    from app.application.dtos.ai import ProviderConfig

    config = ProviderConfig(
        provider_id="p", kind="openai", model="m", base_url="http://x/v1",
        max_tokens=512, keep_alive="30m",
    )
    provider = OpenAIProvider(config)
    body = provider._request_body(
        GenerationPrompt(user="q", max_tokens=512), stream=True
    )
    assert body.get("keep_alive") == "30m"
    assert body.get("max_tokens") == 512
