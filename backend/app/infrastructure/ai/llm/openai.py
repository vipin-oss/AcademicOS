"""OpenAI-compatible LanguageModelGateway adapter (Sprint M11.2 — ADR-001).

THE single owner of generative-LLM transport in AcademicOS. The production
OpenAI-compatible chat-completions call lives here, and only here: the
assistant's ``LlmAssistantProvider`` is now a thin translator that delegates
to a ``LanguageModelGateway`` (this class) and owns no transport of its own,
and the AI Core catalogue builds this same class from ``AI_PROVIDERS_JSON``.
One transport, one abstraction (ADR-001 goals 1 & 2).

Behaviour (faithfully relocated from the former ``LlmAssistantProvider``
transport so no product behaviour changes — Sprint M11.2 goal 6):

- Deterministic request construction: fixed JSON body (``model``,
  ``messages`` [system, user], ``temperature: 0``), no sampling randomness.
  ``GenerationPrompt.extra_body`` (if any) is merged in — the assistant
  attaches its numbered evidence this way, preserving the exact prior wire
  format.
- Timeout: configurable, applied to every attempt.
- Retries: bounded with FIXED backoff, ONLY for transient failures —
  transport errors (connect / timeout) and HTTP 5xx. 4xx (bad request /
  auth) and malformed responses raise immediately.
- After the retry bound is spent the adapter raises ``LlmProviderError``;
  the composition layer (``FallbackAssistantProvider``) converts that into
  the deterministic rules fallback — the assistant never crashes.

Adapter-independence guardrail: this module imports no sibling adapter and
no infrastructure outside ``app.infrastructure.ai`` — it is self-contained
(the architecture test ``test_ai_guardrails`` enforces this). It therefore
re-implements the honest "not configured" surface itself rather than sharing
the placeholder base class.

No SDK; httpx only (already a dependency). No credentials are logged.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Iterator

import httpx

from app.application.ai.errors import AiNotConfiguredError
from app.application.ai.llm.estimates import estimate_cost_usd, estimate_tokens
from app.application.dtos.ai import (
    KIND_CAPABILITIES,
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

# Bounded, fixed backoff — deterministic by contract (the repository's
# lock-retry doctrine applied to the external call).
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5
# Non-retryable client errors (bad request, auth, not found, ...).
_NO_RETRY_STATUS = frozenset({400, 401, 403, 404, 422, 429})


class LlmProviderError(RuntimeError):
    """The LLM endpoint could not produce a result (after retries)."""


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class OpenAIProvider:
    """OpenAI-compatible generative gateway (implements ``LanguageModelGateway``).

    When configured (a ``base_url`` is present) it performs real
    chat-completions calls over httpx. When not configured it behaves as the
    honest "not configured" gateway — ``health`` reports ``not_configured``
    and generation raises :class:`AiNotConfiguredError` — so the AI Core
    catalogue and the assistant both see one consistent provider object
    whether or not an endpoint is wired.
    """

    provider_id = PROVIDER_KIND_OPENAI
    display_name = "OpenAI"
    kind = PROVIDER_KIND_OPENAI
    capabilities = KIND_CAPABILITIES[PROVIDER_KIND_OPENAI]

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        client: httpx.Client | None = None,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._config = config
        # ``client`` is injectable so tests can drive a MockTransport; when
        # absent the adapter builds (and owns) its own authenticated client.
        self._client = client
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    # ------------------------------------------------------------- identity
    @property
    def model(self) -> str:
        return self._config.model if self._config is not None else ""

    @property
    def _is_configured(self) -> bool:
        return self._config is not None and bool(self._config.base_url)

    def _client_or_build(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        api_key = self._config.api_key if self._config is not None else ""
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        timeout = self._config.timeout_seconds if self._config is not None else 30.0
        return httpx.Client(timeout=timeout, headers=headers)

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
        """One complete generation. Raises ``AiNotConfiguredError`` when no
        endpoint is wired; ``LlmProviderError`` on transport failure."""
        if not self._is_configured:
            raise self._not_configured()
        text = self._complete(prompt)
        return GenerationResult(
            text=text,
            model=self._config.model,
            finish_reason="stop",
            usage=TokenUsage(estimated=True),
            latency_ms=0,
        )

    def stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        """Stream tokens, then one ``complete`` event.

        Raises ``AiNotConfiguredError`` immediately when no endpoint is
        wired; ``LlmProviderError`` on a failure (before or mid-stream).
        Implemented as a plain method that guards then returns the generator,
        so the not-configured check fires at call time (not lazily on first
        iteration) - parity with the placeholder contract.
        """
        if not self._is_configured:
            raise self._not_configured()
        return self._stream(prompt)

    def structured_generate(
        self, prompt: StructuredGenerationPrompt
    ) -> StructuredGenerationResult:
        # Not configured -> the honest not-configured state (parity with the
        # other gateway operations). Configured but unsupported in M11.2 ->
        # an explicit, honest error (no fake structured output).
        if not self._is_configured:
            raise self._not_configured()
        del prompt
        raise LlmProviderError(
            "Structured generation is not supported by the OpenAI gateway "
            "adapter in this release."
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
    def _request_body(self, prompt: GenerationPrompt, *, stream: bool) -> dict:
        """The deterministic request body — ONE construction site for the
        sync and streaming paths. ``extra_body`` (if any) is merged in so a
        composed feature can attach provider-agnostic request metadata."""
        body = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": 0,
            "stream": stream,
        }
        if prompt.extra_body:
            body.update(prompt.extra_body)
        return body

    def _complete(self, prompt: GenerationPrompt) -> str:
        body = self._request_body(prompt, stream=False)
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
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
            return self._parse(response)
        raise LlmProviderError(f"LLM request failed: {last_error}")  # pragma: no cover

    def _stream(self, prompt: GenerationPrompt) -> Iterator[GenerationEvent]:
        body = self._request_body(prompt, stream=True)
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        client = self._client_or_build()
        chunks: list[str] = []
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
                        delta = self._extract_delta(payload)
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
                            finish_reason="stop",
                            usage=TokenUsage(estimated=True),
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

    @staticmethod
    def _extract_delta(payload: str) -> str:
        """The text of one SSE data chunk (OpenAI delta or message form)."""
        try:
            data = json.loads(payload)
            choice = data["choices"][0]
            delta = choice.get("delta") or choice.get("message") or {}
            content = delta.get("content")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("LLM stream had an unexpected shape.") from exc
        return str(content) if content else ""

    @staticmethod
    def _parse(response: httpx.Response) -> str:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("LLM response had an unexpected shape.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmProviderError("LLM response contained no text.")
        return content.strip()

    # ----------------------------------------------------------- internals
    def _not_configured(self) -> AiNotConfiguredError:
        return AiNotConfiguredError(
            f"Provider '{self.provider_id}' is not configured: no base_url is "
            f"set for kind '{self.kind}' (planned for a later M11 sprint)."
        )
