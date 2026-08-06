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
    CONTEXT_MEMORY_CHAR_BUDGET,
    AssistantContext,
    AssistantRetrievalResult,
    KnowledgeItem,
    MemoryItem,
    MemoryRecall,
    RetrievedItem,
)
from app.application.use_cases.assistant.helpers import read_messages
from app.domain.entities.object import UniversalObject


def _chars(*parts: str) -> int:
    return sum(len(part) for part in parts)


class AssistantContextBuilder:
    """Composes history + retrieval + memory into one bounded envelope."""

    def __init__(
        self,
        *,
        context_budget: int = CONTEXT_CHAR_BUDGET,
        history_budget: int = CONTEXT_HISTORY_CHAR_BUDGET,
        memory_budget: int = CONTEXT_MEMORY_CHAR_BUDGET,
    ) -> None:
        self._context_budget = context_budget
        self._history_budget = history_budget
        self._memory_budget = memory_budget

    def build(
        self,
        conversation: UniversalObject | None,
        question: str,
        retrieval: AssistantRetrievalResult | None,
        *,
        memory: MemoryRecall | None = None,
    ) -> AssistantContext:
        """Deterministic context for one question.

        ``conversation`` may be ``None`` (first turn of a new thread);
        ``retrieval`` may be ``None`` (retrieval unavailable — the context
        then carries history alone). ``memory`` (Sprint-8 M2) is the
        automatic memory recall — recalled conversations and the
        graph-discovered knowledge objects — trimmed to the memory
        budget; ``None`` keeps the pre-M2 envelope (empty memory fields).
        """
        history = self._trim_history(conversation)
        memories, knowledge, memory_truncated = self._trim_memory(
            memory, self._memory_budget
        )
        remaining = max(self._context_budget - _chars(question, *[c for _r, c in history]), 0)
        retrieved, retrieved_truncated = self._trim_retrieval(retrieval, remaining)
        return AssistantContext(
            question=question,
            history=tuple(history),
            retrieved=tuple(retrieved),
            memories=tuple(memories),
            knowledge=tuple(knowledge),
            truncated=retrieved_truncated or self._history_trimmed or memory_truncated,
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

    @staticmethod
    def _trim_memory(
        memory: MemoryRecall | None, budget: int
    ) -> tuple[list[MemoryItem], list[KnowledgeItem], bool]:
        """Recalled memories + knowledge trimmed to the memory budget.

        Deterministic: memories are kept head-first in recall order (the
        most relevant first), knowledge fills the remainder — trimming
        drops the LEAST relevant content, mirroring the retrieval
        doctrine.
        """
        if memory is None:
            return [], [], False
        kept_memories: list[MemoryItem] = []
        kept_knowledge: list[KnowledgeItem] = []
        used = 0
        truncated = False
        for item in memory.conversations:
            cost = _chars(item.title, item.question, item.answer)
            if used + cost > budget:
                truncated = True
                break
            kept_memories.append(item)
            used += cost
        for item in memory.knowledge:
            cost = _chars(item.object_id, item.title)
            if used + cost > budget:
                truncated = True
                break
            kept_knowledge.append(item)
            used += cost
        return kept_memories, kept_knowledge, truncated


__all__ = ["AssistantContextBuilder"]
