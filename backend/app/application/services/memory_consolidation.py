"""Memory consolidation & forgetting (Sprint-8 M4).

Keeps the memory base clean by detecting redundant conversations and
marking the obsolete ones SUPERSEDED, never deleting anything.

- Duplicate detection uses normalized question equality and deterministic
  token-Jaccard answer similarity.
- Canonical choice prefers approved review > unreviewed >
  pending/rejected, with newest created_at winning ties.
- Superseding uses the existing UniversalObject.supersede() domain
  primitive.
- SUPERSEDED conversations remain fully intact and are excluded from
  normal memory recall.
- Consolidation is an explicit operator-triggered operation and never
  runs inside the read/ask path.
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


# The answer-similarity threshold for "near-identical" memories.
# Jaccard similarity is computed over lowercased tokens.
DUPLICATE_ANSWER_SIMILARITY = 0.7


# Canonical-choice quality:
# approved > unreviewed > pending/rejected.
#
# Within the same review-quality level, the newest created_at wins.
_REVIEW_QUALITY = {
    dto.REVIEW_APPROVED: 2,
    "": 1,
    dto.REVIEW_PENDING: 0,
    dto.REVIEW_REJECTED: 0,
}


@dataclass(frozen=True)
class ConsolidatedPair:
    """One superseded memory and the canonical memory that replaced it."""

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
    """Return deterministic token-Jaccard similarity in [0, 1]."""
    tokens_a = _tokens(a)
    tokens_b = _tokens(b)

    if not tokens_a and not tokens_b:
        return 1.0

    if not tokens_a or not tokens_b:
        return 0.0

    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _last_question(obj: UniversalObject) -> str:
    user_messages = [
        payload
        for _seq, payload in read_messages(obj)
        if payload.get("role") == "user"
    ]

    if not user_messages:
        return ""

    return str(user_messages[-1].get("content") or "")


def _last_answer(obj: UniversalObject) -> str:
    assistant_messages = [
        payload
        for _seq, payload in read_messages(obj)
        if payload.get("role") == "assistant"
    ]

    if not assistant_messages:
        return ""

    return str(assistant_messages[-1].get("content") or "")


class MemoryConsolidationService:
    """The single consolidation seam for conversation-memory deduplication."""

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
        """Run one deterministic consolidation pass.

        ACTIVE conversations are grouped by near-duplicate question and
        answer. Each group keeps exactly one canonical conversation.

        Canonical selection is based on:
        1. review quality;
        2. newest created_at for equal review quality.

        All other members are marked SUPERSEDED.
        """
        conversations = all_conversations(self._repository)

        active = [
            obj
            for obj in conversations
            if obj.status is ObjectStatus.ACTIVE
        ]

        # Stable chronological traversal.
        active.sort(
            key=lambda obj: (
                obj.audit.created_at if obj.audit else "",
                str(obj.id),
            )
        )

        # Deterministic grouping.
        #
        # The first member seeds a group. Later members join when they
        # have the same normalized question and sufficiently similar
        # answers.
        groups: dict[str, list[UniversalObject]] = {}
        order: list[str] = []

        for obj in active:
            question = _normalize_question(_last_question(obj))

            if not question:
                continue

            answer = _last_answer(obj)
            matched: str | None = None

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

            # Canonical policy:
            #   1. review quality
            #   2. newest created_at
            #
            # Do NOT use object ID as a proxy for creation order.
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