"""Port: the assistant's answering engine seam (future-LLM ready).

Version 1 ships exactly one adapter: ``RuleBasedAssistantProvider`` (local,
deterministic — no external AI of any kind; see the module brief). A future
LLM adapter (OpenAI / Gemini / a campus-hosted model — whatever the
institution later sanctions) plugs in by implementing this same protocol and
is selected at composition time in the route dependency, with ZERO changes to
the routes, use cases, or contracts. This is the FileStorage doctrine
(local adapter first, swap at the edge) applied to intelligence.
"""
from __future__ import annotations

from typing import Protocol

from app.application.dtos.assistant import AssistantAnswerOutput


class AssistantProvider(Protocol):
    """Answers one natural-language question against AcademicOS data."""

    @property
    def name(self) -> str:
        """Provider id recorded on answers for auditability (e.g. 'rules-v1')."""
        ...

    def answer(self, question: str, asked_by: str) -> AssistantAnswerOutput:
        """Produce a deterministic, data-grounded answer. Never raises for a
        well-formed question — unknowns degrade to knowledge search results."""
        ...
