"""Port: assistant memory retrieval (Sprint-8 M1).

The single seam between conversation memory and any future consumer —
including RAG pipelines. Mirrors the ``AssistantProvider`` doctrine: a
Protocol, structurally implemented by the memory service, so a future
RAG adapter (cross-conversation memory, external knowledge, ...) plugs
in at composition time with zero changes to callers.

Contract: ``recall`` returns the deterministic memory recall for one
question — recalled conversations (already permission-filtered and
review-gated) plus the graph-discovered knowledge objects.
"""
from __future__ import annotations

from typing import Protocol

from app.application.dtos.assistant import MemoryRecall
from app.domain.entities.object import UniversalObject


class AssistantMemoryRetriever(Protocol):
    """Retrieves assistant memory relevant to one question."""

    def recall(
        self,
        query: str,
        user: UniversalObject,
        *,
        limit: int = 10,
        exclude_conversation_id: str | None = None,
    ) -> MemoryRecall:
        """The memory recall for ``query`` as seen by ``user``.

        ``user`` is the authenticated principal: its READ permissions gate
        every recalled item inside the reused retrieval consumers.
        ``exclude_conversation_id`` drops one conversation from the
        recalled memories (the ask pipeline excludes the current thread).
        The result is deterministic (fixed ordering, no randomness).
        """
        ...
