"""OpenAI-compatible embedding adapter (Sprint M12.2 — ADR-001).

Implements the **existing** ``Embedder`` port (``application/ports/embedder.py``)
— NOT a sibling abstraction. The AI Core resolves this adapter (or the
``HashingEmbedder`` fallback) through ``AiCore.embedder()``, so the entire
search stack (``SearchObjectsUseCase``, ``SearchIndexApplier``, Qdrant) uses
one consistent embedding identity for both indexing and querying.

Transport mirrors ``OpenAIProvider``: httpx, bounded retries with fixed backoff,
non-retryable status set, ``LlmProviderError`` on failure, lazy owned client
with ``close()``. No SDK. No credentials logged.
"""
from __future__ import annotations

import time

import httpx

from app.application.dtos.ai import ProviderConfig
from app.application.ports.embedder import Embedder

__all__ = ["OpenAIEmbeddingAdapter"]

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.5
_NO_RETRY_STATUS = frozenset({400, 401, 403, 404, 422, 429})


class _EmbeddingError(RuntimeError):
    """The embedding endpoint could not produce a vector (after retries)."""


class OpenAIEmbeddingAdapter(Embedder):
    """Real embedding adapter behind the existing ``Embedder`` port.

    Calls ``{base_url}/embeddings`` with the provider's ``embedding_model``.
    ``dimensions`` comes from ``ProviderConfig.embedding_dimensions`` (the
    operator declares it — no network call needed at startup, consistent with
    the Qdrant collection-creation contract that calls ``dimensions`` before
    any embedding).
    """

    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
        retry_attempts: int = _RETRY_ATTEMPTS,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._config = config
        self._client = client  # injectable for tests (MockTransport)
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._owned_client: httpx.Client | None = None

    @property
    def dimensions(self) -> int:
        dim = self._config.embedding_dimensions
        if dim and dim > 0:
            return dim
        raise ValueError(
            f"Embedding dimensions not configured for provider "
            f"'{self._config.provider_id}'. Set 'embedding_dimensions' in "
            f"AI_PROVIDERS_JSON."
        )

    def embed(self, text: str) -> list[float]:
        url = f"{self._config.base_url.rstrip('/')}/embeddings"
        body = {"model": self._config.embedding_model, "input": text}
        client = self._client_or_build()
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                response = client.post(url, json=body)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self._retry_attempts - 1:
                    raise _EmbeddingError(
                        f"Embedding endpoint unreachable after "
                        f"{self._retry_attempts} attempts: {exc}"
                    ) from exc
                time.sleep(self._retry_backoff_seconds)
                continue
            if response.status_code in _NO_RETRY_STATUS:
                raise _EmbeddingError(
                    f"Embedding endpoint rejected the request "
                    f"(HTTP {response.status_code})."
                )
            if response.status_code >= 500:
                last_error = _EmbeddingError(
                    f"Embedding endpoint error (HTTP {response.status_code})."
                )
                if attempt == self._retry_attempts - 1:
                    raise last_error
                time.sleep(self._retry_backoff_seconds)
                continue
            if response.status_code != 200:
                raise _EmbeddingError(
                    f"Embedding endpoint returned HTTP {response.status_code}."
                )
            vector = self._parse(response)
            self._validate_dimensions(vector)
            return vector
        raise _EmbeddingError(f"Embedding request failed: {last_error}")

    # ------------------------------------------------------------- lifecycle
    def _client_or_build(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned_client is None:
            api_key = self._config.api_key
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            self._owned_client = httpx.Client(
                timeout=self._config.timeout_seconds, headers=headers
            )
        return self._owned_client

    def close(self) -> None:
        if self._owned_client is not None:
            self._owned_client.close()
            self._owned_client = None

    # ------------------------------------------------------------- parsing
    @staticmethod
    def _parse(response: httpx.Response) -> list[float]:

        try:
            data = response.json()
            embedding = data["data"][0]["embedding"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise _EmbeddingError(
                "Embedding response had an unexpected shape."
            ) from exc
        if not isinstance(embedding, list) or not embedding:
            raise _EmbeddingError("Embedding response contained no vector.")
        return [float(x) for x in embedding]

    def _validate_dimensions(self, vector: list[float]) -> None:
        """Fail immediately if the returned vector length differs from the
        configured dimensions — never return an invalid vector (M12.2.1)."""
        expected = self._config.embedding_dimensions
        if expected is not None and expected > 0 and len(vector) != expected:
            raise _EmbeddingError(
                f"Embedding dimension mismatch: configured {expected}, "
                f"received {len(vector)}. The embedding model or configuration "
                f"is inconsistent."
            )
