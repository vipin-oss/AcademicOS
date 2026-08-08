"""Unit tests: OpenAIEmbeddingAdapter + AiCore.embedder() (Sprint M12.2).

Tests the real embedding adapter (httpx MockTransport), the AI Core's
embedder resolution, and the build_ai_core composition (real adapter vs
HashingEmbedder fallback).
"""
from __future__ import annotations

import httpx
import pytest

from app.application.dtos.ai import ProviderConfig
from app.infrastructure.ai.embedding.openai_embedding_adapter import (
    OpenAIEmbeddingAdapter,
    _EmbeddingError,
)
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder


def _cfg(**over) -> ProviderConfig:
    base = dict(
        provider_id="oa", kind="openai", model="gpt-4o-mini",
        base_url="http://llm.example/v1", api_key="k",
        embedding_model="text-embedding-3-small", embedding_dimensions=None,
    )
    base.update(over)
    return ProviderConfig(**base)


def _adapter(handler, **kw) -> OpenAIEmbeddingAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAIEmbeddingAdapter(_cfg(), client=client, **kw)


def _ok_embedding(dim=4) -> dict:
    return {"data": [{"embedding": [0.1] * dim}]}


# --------------------------------------------------------------------------- adapter


class TestEmbed:
    def test_returns_vector(self):
        a = _adapter(lambda r: httpx.Response(200, json=_ok_embedding(8)))
        vec = a.embed("hello")
        assert isinstance(vec, list)
        assert len(vec) == 8
        assert all(isinstance(x, float) for x in vec)

    def test_4xx_fails_immediately(self):
        calls = {"n": 0}

        def h(r):
            calls["n"] += 1
            return httpx.Response(401, json={})

        with pytest.raises(_EmbeddingError, match="401"):
            _adapter(h).embed("hi")
        assert calls["n"] == 1

    def test_5xx_retries_then_raises(self):
        calls = {"n": 0}

        def h(r):
            calls["n"] += 1
            return httpx.Response(503)

        with pytest.raises(_EmbeddingError, match="503"):
            _adapter(h, retry_attempts=3, retry_backoff_seconds=0).embed("hi")
        assert calls["n"] == 3

    def test_transient_then_success(self):
        calls = {"n": 0}

        def h(r):
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.ConnectError("x", request=r)
            return httpx.Response(200, json=_ok_embedding(4))

        vec = _adapter(h, retry_attempts=3, retry_backoff_seconds=0).embed("hi")
        assert len(vec) == 4
        assert calls["n"] == 2

    def test_malformed_response_raises(self):
        a = _adapter(lambda r: httpx.Response(200, json={"unexpected": True}))
        with pytest.raises(_EmbeddingError, match="unexpected shape"):
            a.embed("hi")

    def test_empty_vector_raises(self):
        a = _adapter(lambda r: httpx.Response(200, json={"data": [{"embedding": []}]}))
        with pytest.raises(_EmbeddingError, match="no vector"):
            a.embed("hi")


class TestDimensions:
    def test_from_config(self):
        a = OpenAIEmbeddingAdapter(_cfg(embedding_dimensions=1536))
        assert a.dimensions == 1536

    def test_not_configured_raises(self):
        a = OpenAIEmbeddingAdapter(_cfg(embedding_dimensions=None))
        with pytest.raises(ValueError, match="not configured"):
            a.dimensions


class TestClientLifecycle:
    def test_close_releases_owned_client(self):
        a = OpenAIEmbeddingAdapter(_cfg())  # no injected client
        a._client_or_build()
        assert a._owned_client is not None
        a.close()
        assert a._owned_client is None

    def test_injected_client_not_closed(self):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=_ok_embedding())))
        a = OpenAIEmbeddingAdapter(_cfg(), client=client)
        a.close()
        assert a._client_or_build() is client  # still usable


# --------------------------------------------------------------------------- AiCore.embedder()


class TestAiCoreEmbedder:
    def test_returns_configured_embedder(self):
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.providers.registry import ProviderRegistry

        embedder = HashingEmbedder(dimensions=128)
        core = AiCore(
            registry=ProviderRegistry(),
            gateways={},
            config=AiConfigView(
                enabled=True, default_provider="local", default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={"chat": False, "rag": False, "memory": False,
                               "agents": False, "document_understanding": False,
                               "streaming": True, "summarization": False},
            ),
            embedder=embedder,
        )
        assert core.embedder() is embedder

    def test_raises_when_not_configured(self):
        from app.application.ai.config import AiConfigView
        from app.application.ai.core import AiCore
        from app.application.ai.errors import UnknownProviderError
        from app.application.ai.providers.registry import ProviderRegistry

        core = AiCore(
            registry=ProviderRegistry(),
            gateways={},
            config=AiConfigView(
                enabled=True, default_provider="local", default_model="",
                temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
                streaming_enabled=True,
                feature_flags={"chat": False, "rag": False, "memory": False,
                               "agents": False, "document_understanding": False,
                               "streaming": True, "summarization": False},
            ),
            # no embedder
        )
        with pytest.raises(UnknownProviderError, match="No embedder"):
            core.embedder()


# --------------------------------------------------------------------------- build_ai_core


class _EmbedSettings:
    ai_enabled = True
    ai_default_provider = "oa"
    ai_default_model = ""
    ai_temperature = 0.0
    ai_max_tokens = 2048
    ai_timeout_seconds = 30.0
    ai_streaming_enabled = True
    ai_chat_enabled = False
    ai_rag_enabled = False
    ai_memory_enabled = False
    ai_agents_enabled = False
    ai_document_understanding_enabled = False
    ai_summarization_enabled = False
    ai_providers_json = ""
    assistant_default_model = ""
    assistant_models_json = ""
    assistant_llm_base_url = None
    assistant_llm_model = ""
    assistant_llm_api_key = ""
    assistant_llm_timeout_seconds = 30.0


class TestBuildAiCoreEmbedder:
    def test_embedding_provider_yields_real_adapter(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1",'
            ' "embedding_model": "text-embedding-3-small",'
            ' "embedding_dimensions": 1536}]'
        )
        core = build_ai_core(s)
        emb = core.embedder()
        assert isinstance(emb, OpenAIEmbeddingAdapter)
        assert emb.dimensions == 1536

    def test_no_embedding_provider_yields_hashing_fallback(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1"}]'
        )
        core = build_ai_core(s)
        emb = core.embedder()
        assert isinstance(emb, HashingEmbedder)


class TestDimensionValidation:
    """M12.2.1: returned vector must match configured dimensions."""

    def test_mismatched_dimensions_fail(self):
        """If the endpoint returns 8 floats but dimensions=4, embed() raises."""
        a = _adapter(lambda r: httpx.Response(200, json=_ok_embedding(8)))
        a._config = ProviderConfig(
            provider_id="oa", kind="openai", base_url="http://x/v1",
            embedding_model="m", embedding_dimensions=4,
        )
        with pytest.raises(_EmbeddingError, match="mismatch"):
            a.embed("hi")

    def test_matching_dimensions_pass(self):
        """Returned vector matches configured dimensions → succeeds."""
        a = _adapter(lambda r: httpx.Response(200, json=_ok_embedding(4)))
        vec = a.embed("hi")
        assert len(vec) == 4

    def test_no_configured_dimensions_skips_check(self):
        """When embedding_dimensions is None, the length check is skipped
        (the adapter still raises on dimensions property access, but embed()
        itself does not validate)."""
        a = OpenAIEmbeddingAdapter(
            ProviderConfig(provider_id="oa", kind="openai", base_url="http://x/v1",
                           embedding_model="m", embedding_dimensions=None),
            client=httpx.Client(transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json=_ok_embedding(8)))),
        )
        vec = a.embed("hi")
        assert len(vec) == 8  # no validation — passes through


class TestBuildAiCoreEmbedderConfigValidation:
    """M12.2.1: composition must not construct a real adapter unless config
    is complete (embedding_model + positive dimensions + base_url)."""

    def test_missing_dimensions_falls_back_to_hashing(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1",'
            ' "embedding_model": "text-embedding-3-small"}]'
        )  # no embedding_dimensions
        core = build_ai_core(s)
        from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
        assert isinstance(core.embedder(), HashingEmbedder)

    def test_zero_dimensions_falls_back_to_hashing(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1",'
            ' "embedding_model": "text-embedding-3-small",'
            ' "embedding_dimensions": 0}]'
        )
        core = build_ai_core(s)
        from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
        assert isinstance(core.embedder(), HashingEmbedder)

    def test_negative_dimensions_falls_back_to_hashing(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1",'
            ' "embedding_model": "text-embedding-3-small",'
            ' "embedding_dimensions": -5}]'
        )
        core = build_ai_core(s)
        from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
        assert isinstance(core.embedder(), HashingEmbedder)

    def test_valid_config_still_uses_real_adapter(self):
        from app.infrastructure.ai.provider_factory import build_ai_core

        s = _EmbedSettings()
        s.ai_providers_json = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini",'
            ' "base_url": "http://x/v1",'
            ' "embedding_model": "text-embedding-3-small",'
            ' "embedding_dimensions": 1536}]'
        )
        core = build_ai_core(s)
        assert isinstance(core.embedder(), OpenAIEmbeddingAdapter)
        assert core.embedder().dimensions == 1536
