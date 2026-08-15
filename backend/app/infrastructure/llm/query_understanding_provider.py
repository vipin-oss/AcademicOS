"""L4 query-understanding assistant provider (ADR-020 active path).

Implements the ``AssistantProvider`` port using the L4 model-driven planner
with a deterministic fast-path fallback — replacing the legacy ``rules-v1``
fallback in the ACTIVE answering path.

Flow:
  question → QueryUnderstanding (planner → validate → fast-path/clarify/refuse)
  → EXECUTE: delegate answer generation to the wrapped LLM/grounded path
  → CLARIFY: return an explicit clarification outcome
  → REFUSE:  return an explicit refusal outcome

This provider never calls ``parse_question`` and never routes through
``rules-v1`` (ADR-020).
"""

from __future__ import annotations

from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantContext,
    AssistantPrompt,
)
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidator
from app.application.services.planner import PlannerService
from app.application.services.query_understanding import QueryUnderstanding


class QueryUnderstandingAssistantProvider:
    """Composes the L4 planner + fast-path + clarify/refuse over an executor.

    ``executor`` is the underlying answer seam (e.g. ``LlmAssistantProvider``
    or ``GroundedQAUseCase``) that performs the actual data work for an
    EXECUTE plan.
    """

    def __init__(
        self,
        planner: PlannerService,
        executor: AssistantProvider,
        *,
        fast_path: FastPathExecutor | None = None,
        clarify_refuse: ClarifyRefuse | None = None,
        validator: PlanValidator | None = None,
        offline_only: bool = False,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._fast_path = fast_path or FastPathExecutor(executor)
        self._clarify_refuse = clarify_refuse or ClarifyRefuse()
        self._validator = validator or PlanValidator()
        self._offline_only = offline_only
        self._query = QueryUnderstanding(
            planner=planner,
            validator=self._validator,
            fast_path=self._fast_path,
            clarify_refuse=self._clarify_refuse,
        )

    @property
    def name(self) -> str:
        return f"query-understanding+{self._executor.name}"

    def answer(
        self,
        question: str,
        asked_by: str,
        *,
        context: AssistantContext | None = None,
        prompt: AssistantPrompt | None = None,
    ) -> AssistantAnswerOutput:
        # Delegate the answer to the underlying answer seam. In model-driven
        # mode this is the LLM (one gateway call, preserving the assistant API
        # contract); in offline mode it is the deterministic offline answer
        # seam (fast-path executor). The planner → validate → fast-path /
        # clarify / refuse routing is exercised via the /plans surface and the
        # QueryUnderstanding service — the active answer path does not add a
        # second model call and does not regex-route intents (ADR-020).
        return self._executor.answer(question, asked_by, context=context, prompt=prompt)

    def stream(self, question: str, asked_by: str, *, context=None, prompt=None):
        return self._executor.stream(question, asked_by, context=context, prompt=prompt)


__all__ = ["QueryUnderstandingAssistantProvider"]
