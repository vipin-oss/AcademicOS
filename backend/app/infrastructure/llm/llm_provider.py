"""LLM assistant provider — a thin translator over a LanguageModelGateway
(Sprint M11.2 — ADR-001).

ARCHITECTURE CHANGE (ADR-001): this module NO LONGER OWNS TRANSPORT. It maps
the assistant's feature-level contracts (``AssistantPrompt`` →
``AssistantAnswerOutput``) onto the provider-independent
:class:`LanguageModelGateway` (the single transport abstraction in
AcademicOS, realised by :mod:`app.infrastructure.ai.llm.openai`) and back.
httpx, retries, wire-format construction and SSE parsing live **exclusively**
in the gateway; this adapter only translates DTOs. One transport, one
abstraction (goals 1 & 2); the assistant consumes the AI Core's gateway
instead of owning transport (goal 3).

No product behaviour changes (goal 6): the public surface
(``answer``/``stream``/``name``/``PROVIDER_NAME``/``LlmProviderError`` and the
legacy ``(client, model, base_url, ...)`` constructor) is preserved. The
legacy constructor builds the gateway adapter internally and delegates, so
existing call sites and tests keep working unchanged.

``LlmProviderError`` is re-exported from the gateway for backwards
compatibility — tests and the ``FallbackAssistantProvider`` boundary import
it from here.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict

from app.application.dtos.ai import GenerationPrompt, ProviderConfig
from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantContext,
    AssistantPrompt,
)
from app.infrastructure.ai.llm.openai import (
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    LlmProviderError,
    OpenAIProvider,
)

__all__ = ["LlmAssistantProvider", "LlmProviderError", "PROVIDER_NAME"]

PROVIDER_NAME = "llm-v1"


class LlmAssistantProvider:
    """Assistant-facing answering strategy backed by a ``LanguageModelGateway``.

    Transport is delegated — this class owns no httpx, no retries, no wire
    format. It exists to bridge the assistant's prompt/answer contracts and
    the gateway's generation contracts.

    Two construction modes:

    - **Gateway mode (production, M11.2):** ``LlmAssistantProvider(gateway)``
      where ``gateway`` implements :class:`LanguageModelGateway` (today the
      :class:`OpenAIProvider` built by the AI Core catalogue or by the
      assistant factory). The assistant consumes the gateway abstraction.
    - **Legacy mode (backwards compatibility):**
      ``LlmAssistantProvider(client, model=..., base_url=..., ...)``
      accepting an ``httpx.Client`` — builds the gateway adapter internally
      (injecting the caller's client) and delegates. Existing call sites and
      tests that inject a ``MockTransport`` keep working unchanged.
    """

    def __init__(
        self,
        gateway_or_client,
        *,
        model: str | None = None,
        base_url: str | None = None,
        retry_attempts: int = RETRY_ATTEMPTS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        # Duck-typed detection keeps this module free of an httpx import —
        # transport ownership belongs to the gateway alone. A gateway speaks
        # ``generate``/``stream``; an httpx client does not.
        if hasattr(gateway_or_client, "generate") and hasattr(
            gateway_or_client, "stream"
        ):
            self._gateway = gateway_or_client
        else:
            config = ProviderConfig(
                provider_id="openai",
                kind="openai",
                model=model or "",
                base_url=base_url or "",
            )
            self._gateway = OpenAIProvider(
                config,
                client=gateway_or_client,
                retry_attempts=retry_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
            )

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def model(self) -> str:
        return getattr(self._gateway, "model", "") or ""

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
        result = self._gateway.generate(self._to_generation_prompt(prompt))
        return AssistantAnswerOutput(
            intent="llm",
            intent_label="Assistant",
            question=question.strip(),
            summary=result.text,
            sources=["llm"],
            metrics={"provider": PROVIDER_NAME, "model": result.model or self.model},
        )

    def stream(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ) -> Iterator[dict]:
        """Stream partial tokens, then one completion.

        Synchronous iterator over the gateway's event stream, translated back
        into the assistant's wire-event shapes (``{"type": "token", ...}`` /
        ``{"type": "complete", "answer": ...}``). Gateway failures propagate
        as :class:`LlmProviderError` — the composition layer
        (``FallbackAssistantProvider.stream``) converts that into a
        deterministic single completion. ``GeneratorExit`` (client disconnect)
        propagates without being caught.
        """
        del context, asked_by  # transport only: the prompt is the input
        if prompt is None:
            raise LlmProviderError("No prompt supplied to the LLM provider.")
        gen_prompt = self._to_generation_prompt(prompt)
        chunks: list[str] = []
        for event in self._gateway.stream(gen_prompt):
            if event.kind == "token":
                chunks.append(event.delta)
                yield {"type": "token", "delta": event.delta}
            elif event.kind == "complete":
                yield {
                    "type": "complete",
                    "answer": self._build_answer(question, event.result, chunks),
                }
                return
            elif event.kind == "error":
                raise LlmProviderError(event.message or "LLM stream reported an error.")
        raise LlmProviderError("LLM stream ended without a completion event.")

    # ------------------------------------------------------------- mapping
    def _to_generation_prompt(self, prompt: AssistantPrompt) -> GenerationPrompt:
        """AssistantPrompt -> GenerationPrompt.

        The numbered evidence (``prompt.citations``) is attached as
        provider-agnostic ``extra_body`` request metadata, preserving the
        exact prior wire format (the gateway merges it into the request
        body) without leaking an assistant-specific concept into the clean
        gateway contract.
        """
        return GenerationPrompt(
            system=prompt.system,
            user=prompt.user,
            extra_body={"citations": [asdict(citation) for citation in prompt.citations]},
        )

    def _build_answer(
        self,
        question: str,
        result,
        chunks: list[str],
    ) -> AssistantAnswerOutput:
        """Assemble the full answer from the streamed text (same shape the
        sync path produces)."""
        text = "".join(chunks).strip()
        model = (result.model if result is not None else "") or self.model
        return AssistantAnswerOutput(
            intent="llm",
            intent_label="Assistant",
            question=question.strip(),
            summary=text,
            sources=["llm"],
            metrics={"provider": PROVIDER_NAME, "model": model},
        )
