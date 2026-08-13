"""L4 deterministic offline fast-path answerer (ADR-020).

The offline answer seam used as the fast-path executor when no usable LLM
gateway exists. It answers the common data queries deterministically and OFFLINE
(no LLM). It does NOT regex-route intents via ``parse_question`` — the
query-understanding layer routes through the frozen fast-path command set.

For the common data queries the assistant historically answered offline, this
delegates to the deterministic rule-based data answering logic (the fast-path
executor). The active model-driven path (planner) is the primary when an LLM is
available.
"""

from __future__ import annotations

from app.application.assistant.providers import RuleBasedAssistantProvider
from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantContext,
    AssistantPrompt,
)
from app.domain.repositories.object_repository import ObjectRepository


class OfflineFastPathAnswerer:
    """Deterministic offline answering wrapper (fast-path executor)."""

    def __init__(
        self, repository: ObjectRepository, *, permission_evaluator=None
    ) -> None:
        self._rules = RuleBasedAssistantProvider(
            repository, permission_evaluator=permission_evaluator
        )

    @property
    def name(self) -> str:
        return "fast-path-offline"

    def answer(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ) -> AssistantAnswerOutput:
        # The deterministic offline path answers data queries. ``prompt`` is
        # optional (backward compatible); the rule-based answering does not
        # require an LLM prompt.
        return self._rules.answer(question, asked_by, context=context, prompt=prompt)

    def stream(self, question: str, asked_by: str, *, context=None, prompt=None):
        return self._rules.stream(question, asked_by, context=context, prompt=prompt)


__all__ = ["OfflineFastPathAnswerer"]
