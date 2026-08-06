"""Production LLM provider adapter (Sprint-6 M2).

Pure transport behind the existing ``AssistantProvider`` port: maps a
pre-built ``AssistantPrompt`` onto an OpenAI-compatible ``/chat/completions``
request, calls it over httpx (the repository's established HTTP convention
— see ``infrastructure/external/crossref.py``), and parses the reply into
the shared ``AssistantAnswerOutput``. NO business logic, NO retrieval, NO
prompt construction — the Prompt Builder owns that.

Failure doctrine:

- Deterministic request construction: fixed JSON body (``model``,
  ``messages``, ``temperature: 0``), no sampling randomness.
- Timeout: configurable, applied to every attempt.
- Retries: bounded with FIXED backoff (the repository's lock-retry
  convention), ONLY for transient failures — transport errors (connect /
  timeout) and HTTP 5xx. 4xx (bad request / auth) and malformed responses
  raise immediately.
- After the retry bound is spent the adapter raises ``LlmProviderError``;
  the composition layer (``FallbackAssistantProvider``) converts that into
  the deterministic rules fallback — the assistant never crashes.
"""
from __future__ import annotations

import time
from dataclasses import asdict

import httpx

from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantContext,
    AssistantPrompt,
)

PROVIDER_NAME = "llm-v1"

# Bounded, fixed backoff — deterministic by contract (the repository's
# lock-retry doctrine applied to the external call).
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.5
# Non-retryable client errors (bad request, auth, not found, ...).
_NO_RETRY_STATUS = frozenset({400, 401, 403, 404, 422, 429})


class LlmProviderError(RuntimeError):
    """The LLM endpoint could not produce an answer (after retries)."""


class LlmAssistantProvider:
    """OpenAI-compatible chat-completions transport adapter."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        model: str,
        base_url: str,
        retry_attempts: int = _RETRY_ATTEMPTS,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = client
        self._model = model
        self._base_url = (base_url or "").rstrip("/")
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def answer(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ) -> AssistantAnswerOutput:
        del context, asked_by  # transport only: the prompt is the input
        if prompt is None:
            raise LlmProviderError("No prompt supplied to the LLM provider.")
        content = self._complete(prompt)
        return AssistantAnswerOutput(
            intent="llm",
            intent_label="Assistant",
            question=question.strip(),
            summary=content,
            sources=["llm"],
            metrics={"provider": PROVIDER_NAME, "model": self._model},
        )

    # ------------------------------------------------------------- transport
    def _complete(self, prompt: AssistantPrompt) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": 0,
            # S6 M3: the numbered evidence travels with the request so the
            # provider (and any logging/eval layer) can bind citations to
            # the answer — the model may never invent its own.
            "citations": [asdict(citation) for citation in prompt.citations],
        }
        url = f"{self._base_url}/chat/completions"
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                response = self._client.post(url, json=body)
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
