"""Assistant Context Builder (Sprint-6 M1 Phase 2).

Builds the provider-agnostic context envelope for one assistant turn from:

- **conversation history** — the existing ``read_messages`` helper (the
  conversation aggregate's ``msg.<seq>`` metadata), trimmed OLDEST-FIRST to
  the history budget;
- **hybrid search results** — ``AssistantRetrievalResult`` items with
  provenance (search / graph / both), trimmed to the remaining context
  budget;
- **graph results** — merged into the same retrieval envelope by the
  retrieval service (Phase 1).

Budgets are deterministic character budgets (no tokenizer dependency —
CI-safe and stable); trimming always drops the oldest content first.
``truncated`` reports whether any trimming occurred. Pure service — no
provider logic, no persistence.
"""
from __future__ import annotations

from app.application.dtos.assistant import (
    CONTEXT_CHAR_BUDGET,
    CONTEXT_HISTORY_CHAR_BUDGET,
    AssistantContext,
    AssistantRetrievalResult,
    RetrievedItem,
)
from app.application.use_cases.assistant.helpers import read_messages
from app.domain.entities.object import UniversalObject


def _chars(*parts: str) -> int:
    return sum(len(part) for part in parts)


class AssistantContextBuilder:
    """Composes history + retrieval into one bounded context envelope."""

    def __init__(
        self,
        *,
        context_budget: int = CONTEXT_CHAR_BUDGET,
        history_budget: int = CONTEXT_HISTORY_CHAR_BUDGET,
    ) -> None:
        self._context_budget = context_budget
        self._history_budget = history_budget

    def build(
        self,
        conversation: UniversalObject | None,
        question: str,
        retrieval: AssistantRetrievalResult | None,
    ) -> AssistantContext:
        """Deterministic context for one question.

        ``conversation`` may be ``None`` (first turn of a new thread);
        ``retrieval`` may be ``None`` (retrieval unavailable — the context
        then carries history alone).
        """
        history = self._trim_history(conversation)
        remaining = max(self._context_budget - _chars(question, *[c for _r, c in history]), 0)
        retrieved, retrieved_truncated = self._trim_retrieval(retrieval, remaining)
        return AssistantContext(
            question=question,
            history=tuple(history),
            retrieved=tuple(retrieved),
            truncated=retrieved_truncated or self._history_trimmed,
        )

    # ---------------------------------------------------------------- parts
    def _trim_history(
        self, conversation: UniversalObject | None
    ) -> list[tuple[str, str]]:
        """Newest-tail history: trimming drops the OLDEST content first."""
        self._history_trimmed = False
        if conversation is None:
            return []
        pairs: list[tuple[str, str]] = []
        for _seq, payload in read_messages(conversation):
            role = str(payload.get("role") or "user")
            content = str(payload.get("content") or "")
            pairs.append((role, content))
        # Iterate NEWEST first, keep what fits, then restore chronological
        # order — the tail survives, the oldest messages are dropped.
        kept: list[tuple[str, str]] = []
        used = 0
        for role, content in reversed(pairs):
            cost = len(content)
            if used + cost > self._history_budget:
                self._history_trimmed = True
                continue
            kept.append((role, content))
            used += cost
        kept.reverse()
        return kept

    @staticmethod
    def _trim_retrieval(
        retrieval: AssistantRetrievalResult | None, budget: int
    ) -> tuple[list[RetrievedItem], bool]:
        """Retrieval items trimmed (in their deterministic order) to fit."""
        if retrieval is None or not retrieval.items:
            return [], False
        kept: list[RetrievedItem] = []
        used = 0
        for item in retrieval.items:
            cost = _chars(item.object_id, item.title)
            if used + cost > budget:
                break
            kept.append(item)
            used += cost
        return kept, len(kept) < len(retrieval.items)


__all__ = ["AssistantContextBuilder"]
