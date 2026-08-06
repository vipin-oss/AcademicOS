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
4. **Review ranking** (Sprint-8 M3) — recalled memories are re-ranked by
   human review history when a ``ReviewDecisionStore`` is wired: approved
   conversations rise, rejected ones fall, pending/unreviewed stay
   neutral (``review_boost``). Stable — ties keep the retrieval order.

The service implements the ``AssistantMemoryRetriever`` port — the
retrieval abstraction reusable by future RAG consumers.
"""
from __future__ import annotations

from dataclasses import replace

from app.application.dtos import assistant as dto
from app.application.ports.assistant_memory import AssistantMemoryRetriever
from app.application.ports.review_decision_store import ReviewDecisionStore
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import (
    REVIEW_RATING_MAX,
    ReviewDecision,
    _review_status,
)
from app.application.use_cases.assistant.helpers import (
    last_message_at,
    message_output,
    read_messages,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId

DEFAULT_MEMORY_LIMIT = 10
DEFAULT_SEARCH_LIMIT = 8
DEFAULT_GRAPH_ANCHORS = 3
DEFAULT_GRAPH_DEPTH = 2


def review_boost(decision: ReviewDecision | None, status: str) -> float:
    """The deterministic ranking contribution of a conversation's review
    history (Sprint-8 M3).

    Learning from human feedback: an APPROVED conversation is boosted by
    ``(rating/5) * confidence`` (defaults 5 and 1.0 — a bare approve is a
    full-strength positive); a REJECTED conversation is penalized by the
    same magnitude (negative). Everything else is NEUTRAL (0.0):

    - ``status`` pending or "" — an unreviewed / re-pended latest answer
      never influences ranking (decisions are only recorded on
      approve/reject, so pending conversations have no decisions by
      construction — this gate also covers a re-pended conversation whose
      earlier answers were reviewed, preventing stale influence);
    - ``decision`` None — a reviewed status without an audit row (legacy
      pre-S7 M5 data): nothing to learn from;
    - ``decision.decision != status`` — a stale mismatch (defensive):
      the live status is the authority.

    Deterministic: a pure function of the immutable decision record.
    """
    if status not in (dto.REVIEW_APPROVED, dto.REVIEW_REJECTED):
        return 0.0
    if decision is None or decision.decision != status:
        return 0.0
    magnitude = (
        (decision.rating or REVIEW_RATING_MAX) / REVIEW_RATING_MAX
    ) * (decision.confidence if decision.confidence is not None else 1.0)
    return magnitude if status == dto.REVIEW_APPROVED else -magnitude


class AssistantMemoryService(AssistantMemoryRetriever):
    """Conversation memory + knowledge recall over the existing engines."""

    def __init__(
        self,
        repository: ObjectRepository,
        retrieval: AssistantRetrievalService,
        *,
        decision_store: ReviewDecisionStore | None = None,
    ) -> None:
        self._repository = repository
        self._retrieval = retrieval
        # Sprint-8 M3 — the review-feedback ranking source. None keeps the
        # pre-M3 recall ordering (backward compatible).
        self._decision_store = decision_store

    def recall(
        self,
        query: str,
        user: UniversalObject,
        *,
        limit: int = DEFAULT_MEMORY_LIMIT,
        exclude_conversation_id: str | None = None,
    ) -> dto.MemoryRecall:
        """The deterministic memory recall for ``query``.

        The search leg is narrowed to conversations; the graph leg then
        discovers related objects from the top conversation anchors.
        ``exclude_conversation_id`` (Sprint-8 M2) drops one conversation
        from the recalled memories — the ask pipeline excludes the
        CURRENT thread so it never appears as its own memory (its history
        is already in the prompt). Permission filtering is NOT duplicated
        here: both legs already apply the shared R4 evaluator, so every
        recalled item has passed it (the same doctrine as
        ``AssistantRetrievalService``).
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
                if exclude_conversation_id and item.object_id == exclude_conversation_id:
                    continue
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
        conversations = self._rank(conversations)
        return dto.MemoryRecall(
            conversations=tuple(conversations),
            knowledge=tuple(knowledge),
            search_count=result.search_count,
            graph_count=result.graph_count,
        )

    # ----------------------------------------------------------- ranking
    def _rank(self, items: list[dto.MemoryItem]) -> list[dto.MemoryItem]:
        """Re-rank recalled memories by human review history (Sprint-8 M3).

        Each memory's ``review_score`` is derived from its LIVE review
        status and the latest matching audit decision (``review_boost``);
        the recall order becomes ``score + review_score`` descending. The
        sort is STABLE — ties keep the deterministic retrieval order.
        Without a decision store the order is the pre-M3 retrieval order
        and every review_score stays 0.0.
        """
        if self._decision_store is None:
            return items
        ranked: list[dto.MemoryItem] = []
        for item in items:
            boost = 0.0
            if item.review_status in (dto.REVIEW_APPROVED, dto.REVIEW_REJECTED):
                decisions = self._decision_store.by_conversation(
                    item.conversation_id
                )
                boost = review_boost(
                    decisions[-1] if decisions else None,
                    item.review_status,
                )
            ranked.append(replace(item, review_score=boost))
        return sorted(
            ranked,
            key=lambda item: item.score + item.review_score,
            reverse=True,
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
        if obj.status is ObjectStatus.SUPERSEDED:
            # Sprint-8 M4 — forgetting: superseded memories (consolidated
            # duplicates) are ignored by default. The live object is the
            # authority; the superseded conversation itself is fully
            # intact (messages, citations, review, ACLs, graph).
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
    "review_boost",
]
