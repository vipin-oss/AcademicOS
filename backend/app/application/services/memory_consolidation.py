"""Memory consolidation & forgetting (Sprint-8 M4).

Keeps the memory base clean by detecting redundant conversations and
marking the obsolete ones SUPERSEDED — never deleting anything:

- **Duplicate detection** — near-identical memories are grouped using
  EXISTING conversation metadata (the same question/answer projection
  ``MemoryItem`` exposes): normalized question equality AND deterministic
  token-Jaccard answer similarity at or above ``DUPLICATE_ANSWER_SIMILARITY``.
- **Canonical choice** — within a group, the member whose content is most
  recallable wins: approved review > unreviewed > pending/rejected
  (a pending or rejected canonical would hide the group's answer content),
  ties broken by newest first. Review history is preserved per
  conversation (immutable ``review_decisions`` rows are never touched).
- **Superseding** — every other member is marked through the EXISTING
  domain primitive ``UniversalObject.supersede(canonical_id, actor)``:
  terminal SUPERSEDED status + a VERSION_OF graph edge to the canonical +
  a durable ``ObjectSuperseded`` outbox event, committed with the
  repository's optimistic concurrency (CAS) — so concurrent runs collapse
  safely (one wins, the other 409s) and nothing is ever deleted. The
  superseded object keeps ALL of its data: messages, citations, review
  status, ACL permissions, graph relationships.
- **Retrieval effect** — the memory service drops SUPERSEDED conversations
  from recall (the live object is the authority), so consolidated memory
  is ignored by default while remaining fully intact.

Consolidation is an explicit, operator-triggered pass (the
``POST /assistant/memory/consolidate`` endpoint) — it never runs inside
the read/ask path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.dtos import assistant as dto
from app.application.services.assistant_review import _review_status
from app.application.use_cases.assistant.helpers import (
    all_conversations,
    read_messages,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus

# The answer-similarity threshold for "near-identical" memories (Jaccard
# over lowercased tokens; deterministic, no embeddings).
DUPLICATE_ANSWER_SIMILARITY = 0.7

# Canonical-choice quality: approved content is fully recallable,
# unreviewed content is recallable, pending/rejected content is hidden by
# the review gate — a canonical in those states would hide the group's
# answer. Ties break by newest first.
_REVIEW_QUALITY = {
    dto.REVIEW_APPROVED: 2,
    "": 1,
    dto.REVIEW_PENDING: 0,
    dto.REVIEW_REJECTED: 0,
}


@dataclass(frozen=True)
class ConsolidatedPair:
    """One superseded memory and the canonical that replaced it."""

    conversation_id: str
    canonical_id: str


@dataclass(frozen=True)
class ConsolidationReport:
    """The deterministic outcome of one consolidation pass."""

    scanned: int
    consolidated: int
    superseded: tuple[ConsolidatedPair, ...] = ()


def _normalize_question(text: str) -> str:
    return " ".join((text or "").casefold().split())


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").casefold()))


def answer_similarity(a: str, b: str) -> float:
    """Deterministic token-Jaccard similarity of two answers in [0, 1]."""
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _last_question(obj: UniversalObject) -> str:
    user_messages = [
        payload for _seq, payload in read_messages(obj) if payload.get("role") == "user"
    ]
    return str(user_messages[-1].get("content") or "") if user_messages else ""


def _last_answer(obj: UniversalObject) -> str:
    assistant_messages = [
        payload
        for _seq, payload in read_messages(obj)
        if payload.get("role") == "assistant"
    ]
    return (
        str(assistant_messages[-1].get("content") or "")
        if assistant_messages
        else ""
    )


class MemoryConsolidationService:
    """The single consolidation seam: deduplicates conversation memory."""

    def __init__(
        self,
        repository: ObjectRepository,
        *,
        similarity_threshold: float = DUPLICATE_ANSWER_SIMILARITY,
    ) -> None:
        self._repository = repository
        self._similarity_threshold = similarity_threshold

    def consolidate(
        self,
        *,
        actor: str = "system",
    ) -> ConsolidationReport:
        """One deterministic consolidation pass over all conversations.

        ACTIVE conversations are grouped by near-duplicate question+answer
        (oldest-first iteration); each group keeps ONE canonical (the most
        recallable, newest on ties) and every other member is superseded
        by it. Already-superseded / archived conversations are never
        touched again (the terminal status is a no-op guard).
        """
        conversations = all_conversations(self._repository)
        active = [
            obj
            for obj in conversations
            if obj.status is ObjectStatus.ACTIVE
        ]
        active.sort(key=lambda obj: (obj.audit.created_at if obj.audit else "", str(obj.id)))

        # Deterministic grouping: the first member seeds a group; every
        # later member with the same normalized question and a similar
        # answer joins it. Groups are keyed by the ANCHOR's object id (the
        # normalized question is not unique — two different questions can
        # normalize identically, and same-question dissimilar answers form
        # separate groups).
        groups: dict[str, list[UniversalObject]] = {}
        order: list[str] = []
        for obj in active:
            question = _normalize_question(_last_question(obj))
            if not question:
                continue  # no retrievable memory content to consolidate
            answer = _last_answer(obj)
            matched = None
            for anchor_id in order:
                anchor = groups[anchor_id][0]
                anchor_answer = _last_answer(anchor)
                if (
                    _normalize_question(_last_question(anchor)) == question
                    and answer_similarity(answer, anchor_answer)
                    >= self._similarity_threshold
                ):
                    matched = anchor_id
                    break
            if matched is None:
                anchor_id = str(obj.id)
                groups[anchor_id] = [obj]
                order.append(anchor_id)
            else:
                groups[matched].append(obj)

        superseded: list[ConsolidatedPair] = []
        for anchor_id in order:
            members = groups[anchor_id]
            if len(members) < 2:
                continue
            canonical = max(
                members,
                key=lambda obj: (
                    _REVIEW_QUALITY.get(_review_status(obj), 1),
                    obj.audit.created_at if obj.audit else "",
                ),
            )
            for member in members:
                if member is canonical:
                    continue
                member.supersede(canonical.id, actor)
                self._repository.save(member)
                superseded.append(
                    ConsolidatedPair(
                        conversation_id=str(member.id),
                        canonical_id=str(canonical.id),
                    )
                )
        return ConsolidationReport(
            scanned=len(active),
            consolidated=len(superseded),
            superseded=tuple(superseded),
        )


__all__ = [
    "ConsolidatedPair",
    "ConsolidationReport",
    "DUPLICATE_ANSWER_SIMILARITY",
    "MemoryConsolidationService",
    "answer_similarity",
]
