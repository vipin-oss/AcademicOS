"""Port: the assistant's answering engine seam (future-LLM ready).

Version 1 ships exactly one adapter: ``RuleBasedAssistantProvider`` (local,
deterministic — no external AI of any kind; see the module brief). A future
LLM adapter (OpenAI / Gemini / a campus-hosted model — whatever the
institution later sanctions) plugs in by implementing this same protocol and
is selected at composition time in the route dependency, with ZERO changes to
the routes, use cases, or contracts. This is the FileStorage doctrine
(local adapter first, swap at the edge) applied to intelligence.

Sprint-6 M1 — the interface is the **complete-response API**: one call in,
one ``AssistantAnswerOutput`` out, provider-independent. The optional
``context`` keyword carries the retrieval envelope (conversation history +
hybrid search + graph results, already permission-filtered and bounded) so
providers answer from grounded, authorized context. **Streaming** (server-sent
chunks of the same ``AssistantAnswerOutput`` contract) is deferred to a later
milestone; the interface is streaming-ready by design — the conversation
persistence (``append_message``) is already the streaming sink, and a future
``stream_answer`` generator will follow this same signature shape.
"""
from __future__ import annotations

from typing import Protocol

from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantContext,
    AssistantPrompt,
)


class AssistantProvider(Protocol):
    """Answers one natural-language question against AcademicOS data.

    Sprint-6 M4 — optional streaming capability. A provider MAY additionally
    expose ``stream(...)`` (below); callers MUST detect it via
    ``getattr(provider, "stream", None)`` and fall back to ``answer`` when
    absent (deterministic single completion). Streaming is strictly
    additive — the synchronous contract is unchanged.
    """

    @property
    def name(self) -> str:
        """Provider id recorded on answers for auditability (e.g. 'rules-v1')."""
        ...

    def answer(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ) -> AssistantAnswerOutput:
        """Produce a deterministic, data-grounded answer. Never raises for a
        well-formed question — unknowns degrade to knowledge search results.

        ``context`` (S6 M1) is the pre-built retrieval envelope; providers
        MUST treat it as grounded, authorized material (it was permission
        filtered upstream) and MAY ignore it when their logic does not need
        retrieval. Backward compatible: callers without a context pass
        nothing.

        ``prompt`` (S6 M2) is the deterministic prompt envelope built by
        the Prompt Builder; transport providers map it onto their wire
        format. Providers MUST NOT construct prompts themselves — prompt
        construction is the Prompt Builder's single responsibility.
        """
        ...

    def stream(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ):
        """OPTIONAL (S6 M4): stream partial tokens, then one completion.

        Yields event dicts with exactly two shapes:

        - ``{"type": "token", "delta": str}`` — one per partial chunk
          (non-empty text only, in wire order);
        - ``{"type": "complete", "answer": AssistantAnswerOutput}`` —
          exactly once, after the final token, carrying the FULL answer
          (the provider assembles it from the streamed text, same as
          ``answer`` would).

        The stream is a synchronous iterator. On failure the provider MUST
        raise (``LlmProviderError`` for the LLM transport); the composition
        layer (``FallbackAssistantProvider.stream``) converts that into a
        deterministic single completion. Cancellation is cooperative:
        closing the iterator (``GeneratorExit``) aborts without further
        events.
        """
        ...
