"""OpenAI-compatible LanguageModelGateway adapter (ADR-001; hardened M11.3).

THE single owner of generative-LLM transport in AcademicOS. The production
OpenAI-compatible chat-completions call lives here, and only here; the AI Core
constructs this class through ``build_gateway`` and nothing else names it.

M11.3 hardening (production readiness — no behaviour regressions):

- **Client lifecycle / connection reuse:** one owned ``httpx.Client`` per
  adapter instance (lazy, cached), reused across calls; ``close()`` releases
  it. An injected client (tests) is used as-is and never closed by the adapter.
- **Generation policy honoured:** ``max_tokens`` and ``temperature`` come from
  ``ProviderConfig`` (the AI Core is the policy authority), with per-prompt
  overrides. Defaults preserve the prior deterministic behaviour (T=0).
- **Honest accounting:** ``finish_reason`` and token ``usage`` are parsed from
  the response when present (``estimated=False``); otherwise the deterministic
  local estimate is used (``estimated=True``). ``latency_ms`` is measured.
- **No faked capabilities:** structured output is implemented (JSON-object
  mode), so ``structured_output`` is a real capability; ``tools`` is NOT
  claimed (function-calling is not implemented).

Doctrine (unchanged): bounded fixed-backoff retries on transient failures only
(transport errors + HTTP 5xx); 4xx and malformed responses raise immediately;
after the retry bound ``LlmProviderError`` is raised and the composition layer
(``FallbackAssistantProvider``) degrades to the deterministic rules fallback.

Adapter-independence guardrail: imports no sibling adapter and no
infrastructure outside ``app.infrastructure.ai`` (``test_ai_guardrails``). No
SDK; httpx only. No credentials are logged.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

from app.application.ai.errors import AiNotConfiguredError
from app.application.ai.llm.estimates import estimate_cost_usd, estimate_tokens
from app.application.dtos.ai import (
    NOT_CONFIGURED_DETAIL,
    PROVIDER_KIND_OPENAI,
    STATUS_CONFIGURED,
    STATUS_NOT_CONFIGURED,
    GenerationEvent,
    GenerationPrompt,
    GenerationResult,
    ModelInfo,
    ProviderConfig,
    ProviderHealth,
    StructuredGenerationPrompt,
    StructuredGenerationResult,
    TokenUsage,
)

__all__ = [
    "LlmProviderError",
    "OpenAIProvider",
    "RETRY_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS",
]

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5
# Non-retryable client errors (bad request, auth, not found, ...).
_NO_RETRY_STATUS = frozenset({400, 401, 403, 404, 422, 429})
# Capabilities this adapter ACTUALLY implements (no faked "tools").
_CAPABILITIES: tuple[str, ...] = ("chat", "stream", "structured_output")


class LlmProviderError(RuntimeError):
    """The LLM endpoint could not produce a result (after retries)."""


@dataclass
class _RawResult:
    """Fields parsed from one (non-streaming) chat-completions response."""

    text: str
    finish_reason: str
    usage: TokenUsage


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class OpenAIProvider:
    """OpenAI-compatible generative gateway (implements ``LanguageModelGateway``).

    When configured (a ``base_url`` is present) it performs real
    chat-completions calls over a reused httpx client. When not configured it
    behaves as the honest "not configured" gateway.
    """

    # ``kind`` is the family (openai); ``provider_id`` (property below) is the
    # configured catalogue identity - they are distinct, and multiple providers
    # of the same kind stay distinguishable by provider_id.
    display_name = "OpenAI"
    kind = PROVIDER_KIND_OPENAI
    # Only the capabilities actually implemented here (ADR-001: do not fake).
    capabilities = _CAPABILITIES

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        client: httpx.Client | None = None,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._config = config
        self._client = client  # injectable for tests (MockTransport)
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        # Lazily-built, reused owned client (connection pooling). Closed by
        # ``close()``; an injected client is owned by the caller, not us.
        self._owned_client: httpx.Client | None = None

    # ------------------------------------------------------------- identity
    @property
    def provider_id(self) -> str:
        """The configured provider identity (the catalogue ``provider_id``),
        NOT the kind. Falls back to the kind only for the unconfigured
        discovery case (no config). Multiple providers of the same kind stay
        distinguishable by provider_id."""
        if self._config is not None and self._config.provider_id:
            return self._config.provider_id
        return self.kind

    @property
    def model(self) -> str:
        return self._config.model if self._config is not None else ""

    @property
    def _is_configured(self) -> bool:
        return self._config is not None and bool(self._config.base_url)

    def _client_or_build(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned_client is None:
            api_key = self._config.api_key if self._config is not None else ""
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            timeout = self._config.timeout_seconds if self._config is not None else 30.0
            self._owned_client = httpx.Client(timeout=timeout, headers=headers)
        return self._owned_client

    def close(self) -> None:
        """Release the owned httpx client (if any). Idempotent. An injected
        client is NOT closed here — its lifecycle belongs to the caller."""
        if self._owned_client is not None:
            self._owned_client.close()
            self._owned_client = None

    # ------------------------------------------------------------- health
    def health(self) -> ProviderHealth:
        models = self.list_models()
        if self._is_configured:
            return ProviderHealth(
                provider_id=self.provider_id,
                display_name=self.display_name,
                kind=self.kind,
                status=STATUS_CONFIGURED,
                configured=True,
                models_configured=len(models),
                detail="OpenAI-compatible endpoint configured (base_url is set).",
                checked_at=_utcnow_iso(),
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            display_name=self.display_name,
            kind=self.kind,
            status=STATUS_NOT_CONFIGURED,
            configured=False,
            models_configured=len(models),
            detail=NOT_CONFIGURED_DETAIL.format(
                provider_id=self.provider_id, kind=self.kind
            ),
            checked_at=_utcnow_iso(),
        )

    def list_models(self) -> tuple[ModelInfo, ...]:
        if self._config is None or not self._config.model:
            return ()
        return (
            ModelInfo(
                provider_id=self._config.provider_id,
                model_id=self._config.model,
                display_name=self._config.model,
                capabilities=self.capabilities,
                configured=self._is_configured,
            ),
        )

    # ---------------------------------------------------------- generation
    def generate(self, prompt: GenerationPrompt) -> GenerationResult:
        """One complete generation. ``AiNotConfiguredError`` when no endpoint
        is wired; ``LlmProviderError`` on transport failure."""
        if not self._is_configured:
            raise self._not_configured()
        start = time.perf_counter()
        raw = self._post(self._request_body(prompt, stream=False))
        return GenerationResult(
            text=raw.text,
            model=self._config.model,
            finish_reason=raw.finish_reason,
            usage=raw.usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    def stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        """Stream tokens, then one ``complete`` event.

        Raises ``AiNotConfiguredError`` at call time when no endpoint is wired;
        ``LlmProviderError`` on failure. Plain method (guard + return) so the
        not-configured check is eager (parity with the placeholder contract).
        """
        if not self._is_configured:
            raise self._not_configured()
        return self._stream(prompt)

    def structured_generate(
        self, prompt: StructuredGenerationPrompt
    ) -> StructuredGenerationResult:
        """One structured generation against the caller's JSON schema.

        Implemented (M11.3) via JSON-object response mode: the schema is
        asserted to the model through the output contract and the response is
        parsed as JSON. No faked capability — ``structured_output`` is real.
        """
        if not self._is_configured:
            raise self._not_configured()
        body = self._request_body(prompt, stream=False, structured=True)
        start = time.perf_counter()
        raw = self._post(body)
        try:
            value = json.loads(raw.text)
        except ValueError as exc:
            raise LlmProviderError(
                "Structured response was not valid JSON."
            ) from exc
        if not isinstance(value, dict):
            raise LlmProviderError("Structured response was not a JSON object.")
        return StructuredGenerationResult(
            value=value,
            raw_text=raw.text,
            model=self._config.model,
            usage=raw.usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    # ------------------------------------------------------ cost utilities
    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def estimate_cost(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        del model
        return estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)

    # ------------------------------------------------------------- transport
    def _generation_temperature(self, prompt: GenerationPrompt) -> float:
        override = getattr(prompt, "temperature", None)
        if override is not None:
            return float(override)
        return float(self._config.temperature) if self._config is not None else 0.0

    def _generation_max_tokens(self, prompt: GenerationPrompt) -> int | None:
        override = getattr(prompt, "max_tokens", None)
        if override is not None:
            return int(override)
        return int(self._config.max_tokens) if self._config is not None else None

    def _request_body(
        self, prompt: GenerationPrompt, *, stream: bool, structured: bool = False
    ) -> dict:
        """The deterministic request body — ONE construction site for sync,
        streaming and structured paths. ``extra_body`` (if any) is merged in
        so a composed feature can attach provider-agnostic request metadata."""
        body: dict = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": self._generation_temperature(prompt),
            "stream": stream,
        }
        max_tokens = self._generation_max_tokens(prompt)
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            # Ask for usage in the terminal chunk so accounting is honest.
            body["stream_options"] = {"include_usage": True}
        if structured:
            # Broadly-compatible JSON-object mode (OpenAI, vLLM, Ollama, ...).
            body["response_format"] = {"type": "json_object"}
        extra_body = getattr(prompt, "extra_body", None)
        if extra_body:
            body.update(extra_body)
        return body

    def _url(self) -> str:
        return f"{self._config.base_url.rstrip('/')}/chat/completions"

    def _post(self, body: dict) -> _RawResult:
        """One non-streaming call with bounded retries; returns parsed text,
        finish_reason and (real or estimated) usage. Measures latency onto the
        caller's result via the ``latency_ms`` it would carry (set here)."""
        url = self._url()
        client = self._client_or_build()
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                response = client.post(url, json=body)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self._retry_attempts - 1:
                    raise LlmProviderError(
                        f"LLM endpoint unreachable after {self._retry_attempts} attempts: {exc}"
                    ) from exc
                time.sleep(self._retry_backoff_seconds)
                continue
            if response.status_code in _NO_RETRY_STATUS:
                raise LlmProviderError(
                    f"LLM endpoint rejected the request (HTTP {response.status_code})."
                )
            if response.status_code >= 500:
                last_error = LlmProviderError(
                    f"LLM endpoint error (HTTP {response.status_code})."
                )
                if attempt == self._retry_attempts - 1:
                    raise last_error
                time.sleep(self._retry_backoff_seconds)
                continue
            if response.status_code != 200:
                raise LlmProviderError(
                    f"LLM endpoint returned HTTP {response.status_code}."
                )
            return self._parse_response(response)
        raise LlmProviderError(f"LLM request failed: {last_error}")  # pragma: no cover

    def _stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        body = self._request_body(prompt, stream=True)
        url = self._url()
        client = self._client_or_build()
        chunks: list[str] = []
        finish_reason = "stop"
        usage = TokenUsage(estimated=True)
        started = False
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                with client.stream("POST", url, json=body) as response:
                    if response.status_code in _NO_RETRY_STATUS:
                        raise LlmProviderError(
                            f"LLM endpoint rejected the request (HTTP {response.status_code})."
                        )
                    if response.status_code != 200:
                        last_error = LlmProviderError(
                            f"LLM endpoint error (HTTP {response.status_code})."
                        )
                        if attempt < self._retry_attempts - 1:
                            time.sleep(self._retry_backoff_seconds)
                            continue
                        raise last_error
                    started = True  # past the status gate: no more retries
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[len("data:"):].strip()
                        if payload == "[DONE]":
                            break
                        delta, fr, u = self._extract_delta(payload)
                        if fr:
                            finish_reason = fr
                        if u is not None:
                            usage = u
                        if delta:
                            chunks.append(delta)
                            yield GenerationEvent(kind="token", delta=delta)
                    if not chunks:
                        raise LlmProviderError("LLM stream contained no text.")
                    yield GenerationEvent(
                        kind="complete",
                        result=GenerationResult(
                            text="".join(chunks).strip(),
                            model=self._config.model,
                            finish_reason=finish_reason,
                            usage=usage,
                            latency_ms=0,
                        ),
                    )
                    return
            except httpx.HTTPError as exc:
                last_error = exc
                if started or attempt == self._retry_attempts - 1:
                    raise LlmProviderError(
                        f"LLM endpoint unreachable after {self._retry_attempts} attempts: {exc}"
                    ) from exc
                time.sleep(self._retry_backoff_seconds)
        raise LlmProviderError(f"LLM stream failed: {last_error}")  # pragma: no cover

    # ------------------------------------------------------------- parsing
    @staticmethod
    def _extract_delta(payload: str) -> tuple[str, str | None, TokenUsage | None]:
        """One SSE data chunk -> (delta_text, finish_reason, usage_or_None)."""
        try:
            data = json.loads(payload)
        except ValueError as exc:
            raise LlmProviderError("LLM stream had an unexpected shape.") from exc
        delta_text = ""
        finish_reason: str | None = None
        usage: TokenUsage | None = None
        try:
            choices = data.get("choices") or []
            if choices:
                choice = choices[0]
                delta = choice.get("delta") or choice.get("message") or {}
                content = delta.get("content")
                if content:
                    delta_text = str(content)
                fr = choice.get("finish_reason")
                if fr:
                    finish_reason = str(fr)
            if isinstance(data.get("usage"), dict):
                usage = OpenAIProvider._usage_from(data["usage"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("LLM stream had an unexpected shape.") from exc
        return delta_text, finish_reason, usage

    @staticmethod
    def _parse_response(response: httpx.Response) -> _RawResult:
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = str(choice.get("finish_reason") or "stop")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("LLM response had an unexpected shape.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmProviderError("LLM response contained no text.")
        usage = (
            OpenAIProvider._usage_from(data["usage"])
            if isinstance(data.get("usage"), dict)
            else TokenUsage(estimated=True)
        )
        return _RawResult(text=content.strip(), finish_reason=finish_reason, usage=usage)

    @staticmethod
    def _usage_from(raw: dict) -> TokenUsage:
        """Provider-reported usage -> TokenUsage (not estimated)."""
        try:
            return TokenUsage(
                input_tokens=int(raw.get("prompt_tokens", 0) or 0),
                output_tokens=int(raw.get("completion_tokens", 0) or 0),
                estimated=False,
            )
        except (TypeError, ValueError):
            return TokenUsage(estimated=True)

    # ----------------------------------------------------------- internals
    def _not_configured(self) -> AiNotConfiguredError:
        return AiNotConfiguredError(
            f"Provider '{self.provider_id}' is not configured: no base_url is "
            f"set for kind '{self.kind}'."
        )
