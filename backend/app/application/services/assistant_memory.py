"""Assistant Memory Service (Sprint-8 M1).

Pure application service — no prompt construction, no provider calls, no
persistence beyond the reused repository reads. It composes the EXISTING
retrieval pipeline for the memory recall:

1. **Conversation retrieval** — ``AssistantRetrievalService`` with the
   search leg narrowed to ``ai_conversation`` (Sprint-8 M1 object_type
   passthrough): hybrid search + graph runtime, already R4-gated and
   deterministically merged. No search, graph, or merge logic is
   duplicated here.
2. **Hydration** — each recalled conversation object is turned into a
   ``MemoryItem`` using the existing conversation helpers: the latest
   question/answer pair, the CITATIONS preserved from the stored answer
   payload (``message_output`` reconstructs them), the review status and
   the review gate (a pending or rejected answer is recalled with empty
   content and no citations — unapproved content never leaks into
   memory), the retrieval provenance/score, and the last-activity stamp.
3. **Knowledge** — non-conversation objects the graph leg discovered from
   the conversation anchors (graph-aware retrieval) become
   ``KnowledgeItem`` entries.

The service implements the ``AssistantMemoryRetriever`` port — the
retrieval abstraction reusable by future RAG consumers.
"""
from __future__ import annotations

from dataclasses import replace

from app.application.dtos import assistant as dto
from app.application.ports.assistant_memory import AssistantMemoryRetriever
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import _review_status
from app.application.use_cases.assistant.helpers import (
    last_message_at,
    message_output,
    read_messages,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId

DEFAULT_MEMORY_LIMIT = 10
DEFAULT_SEARCH_LIMIT = 8
DEFAULT_GRAPH_ANCHORS = 3
DEFAULT_GRAPH_DEPTH = 2


class AssistantMemoryService(AssistantMemoryRetriever):
    """Conversation memory + knowledge recall over the existing engines."""

    def __init__(
        self,
        repository: ObjectRepository,
        retrieval: AssistantRetrievalService,
    ) -> None:
        self._repository = repository
        self._retrieval = retrieval

    def recall(
        self,
        query: str,
        user: UniversalObject,
        *,
        limit: int = DEFAULT_MEMORY_LIMIT,
    ) -> dto.MemoryRecall:
        """The deterministic memory recall for ``query``.

        The search leg is narrowed to conversations; the graph leg then
        discovers related objects from the top conversation anchors.
        Permission filtering is NOT duplicated here: both legs already
        apply the shared R4 evaluator, so every recalled item has passed
        it (the same doctrine as ``AssistantRetrievalService``).
        """
        result = self._retrieval.retrieve(
            query,
            user,
            object_type=ObjectType.AI_CONVERSATION.value,
            search_limit=DEFAULT_SEARCH_LIMIT,
            graph_anchors=DEFAULT_GRAPH_ANCHORS,
            graph_depth=DEFAULT_GRAPH_DEPTH,
            max_results=limit,
        )
        conversations: list[dto.MemoryItem] = []
        knowledge: list[dto.KnowledgeItem] = []
        for item in result.items:
            if item.object_type == ObjectType.AI_CONVERSATION.value:
                memory = self._hydrate(item)
                if memory is not None:
                    conversations.append(memory)
            else:
                knowledge.append(
                    dto.KnowledgeItem(
                        object_id=item.object_id,
                        object_type=item.object_type,
                        title=item.title,
                        score=item.score,
                        sources=item.sources,
                    )
                )
        return dto.MemoryRecall(
            conversations=tuple(conversations),
            knowledge=tuple(knowledge),
            search_count=result.search_count,
            graph_count=result.graph_count,
        )

    # ----------------------------------------------------------- hydration
    def _hydrate(self, item) -> dto.MemoryItem | None:
        """The memory projection of one recalled conversation object.

        ``None`` when the object no longer exists or is not a conversation
        (the index is derived data; the object is the authority).
        """
        try:
            obj = self._repository.get_by_id(ObjectId(item.object_id))
        except ValueError:
            return None
        if obj is None or obj.object_type is not ObjectType.AI_CONVERSATION:
            return None
        messages = read_messages(obj)
        user_messages = [
            payload for _seq, payload in messages if payload.get("role") == "user"
        ]
        assistant_messages = [
            (_seq, payload)
            for _seq, payload in messages
            if payload.get("role") == "assistant"
        ]
        question = str(user_messages[-1].get("content") or "") if user_messages else ""
        status = _review_status(obj)
        answer = ""
        citations: tuple[dto.AssistantCitation, ...] = ()
        if assistant_messages:
            seq, payload = assistant_messages[-1]
            if status not in (dto.REVIEW_PENDING, dto.REVIEW_REJECTED):
                answer = str(payload.get("content") or "")
                out = message_output(seq, payload)
                if out.answer is not None:
                    # The stored payload round-trips ``sources`` as a list;
                    # the citation DTO declares a tuple — normalize so the
                    # memory projection stays type-honest.
                    citations = tuple(
                        replace(c, sources=tuple(c.sources))
                        for c in out.answer.citations
                    )
        last_stamp = last_message_at(obj)
        return dto.MemoryItem(
            conversation_id=str(obj.id),
            title=obj.title,
            question=question,
            answer=answer,
            citations=citations,
            review_status=status,
            score=item.score,
            sources=item.sources,
            version=item.version or getattr(obj, "version", 1),
            last_message_at=last_stamp.isoformat() if last_stamp else None,
        )


__all__ = [
    "AssistantMemoryService",
    "DEFAULT_GRAPH_ANCHORS",
    "DEFAULT_GRAPH_DEPTH",
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_SEARCH_LIMIT",
]
