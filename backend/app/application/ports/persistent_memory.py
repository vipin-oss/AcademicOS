"""L7 port: persistent memory store (ADR-041).

The single seam for the durable memory layer. Mirrors the
``AssistantMemoryRetriever`` doctrine: a Protocol structurally implemented by the
service, so future consumers (L8 cross-domain) plug in at composition time with
zero changes to callers.

Contract: persistent memory artifacts are created/recalled/forgotten behind this
seam. All reads are ACL-gated to the requesting principal (pre-filter) and review
gated (pending/rejected content is never recalled). Memory is context, never
evidence (ADR-015).
"""

from __future__ import annotations

from typing import Protocol

from app.application.dtos.memory import (
    MemoryArtifact,
    MemoryRecallResult,
    MemoryWriteCommand,
)
from app.domain.entities.object import UniversalObject


class PersistentMemoryStore(Protocol):
    """Creates, recalls, and forgets durable memory artifacts for a principal."""

    def write(
        self, command: MemoryWriteCommand, *, user: UniversalObject
    ) -> MemoryArtifact:
        """Persist one memory artifact authored by ``user``.

        ``user`` is the principal: its id becomes the object owner and its
        identity seeds the ACL scope. Returns the durable artifact.
        """

    def recall(
        self, query: str, user: UniversalObject, *, limit: int = 10
    ) -> MemoryRecallResult:
        """Recall ACL-visible, review-approved memory artifacts for ``query``.

        Deterministic ordering; bounded by ``limit``; pending/rejected content is
        returned with an empty ``answer``.
        """

    def forget(
        self, artifact_id: str, *, user: UniversalObject
    ) -> MemoryArtifact:
        """Mark one durable artifact SUPERSEDED (no delete). Returns it.

        Only the owner (or an authorized manager) may forget an artifact.
        """

    def get(
        self, artifact_id: str, *, user: UniversalObject
    ) -> MemoryArtifact | None:
        """The durable artifact if the principal may READ it, else ``None``."""

    def list(
        self, user: UniversalObject, *, limit: int = 100
    ) -> MemoryRecallResult:
        """The principal's ACL-visible, review-approved artifacts, deterministic."""
