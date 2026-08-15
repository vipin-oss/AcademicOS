"""L7 Memory v2 — persistent memory DTOs (ADR-041).

Additive to the existing assistant memory (Sprint-8). A **memory artifact** is a
durable, principal-scoped container of *recallable context* stored as a
``UniversalObject`` (object_type ``memory_artifact``) on the existing ``objects``
table. It is **context, never evidence** (ADR-015): memory artifacts are never
returned by the L6 citation/evidence contract.

Fields / lifecycle / provenance follow the ratified L7 decision memo:
- provenance: ``ASSERTED`` (user-authored) | ``INFERRED`` (AI-derived) | ``SYSTEM``.
- review status: ``"" | pending | approved | rejected`` (reuse assistant review
  vocabulary). Pending/rejected artifacts recall with empty content.
- supersession/version: reuse ``UniversalObject.supersede`` (no delete).
- ACL: artifact carries ``acl_scope`` for the existing ``PermissionEvaluator``.

Stdlib-only (application layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.value_objects.enums import Provenance

# ---------------------------------------------------------------------------
# Metadata keys on the memory_artifact UniversalObject (L1_SYSTEM layer)
# ---------------------------------------------------------------------------
KEY_MEMORY_QUESTION = "memory.question"
KEY_MEMORY_ANSWER = "memory.answer"
KEY_MEMORY_CONTENT_HASH = "memory.content_hash"
KEY_MEMORY_SOURCE_IDS = "memory.source_ids"  # JSON list of source object ids
KEY_MEMORY_REVIEW_STATUS = "memory.review_status"
KEY_MEMORY_PROVENANCE = "memory.provenance"

# Review status vocabulary (reuse the assistant review constants' values).
REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
_REVIEW_VALUES = {REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED}


@dataclass(frozen=True)
class MemoryArtifact:
    """One durable memory artifact (the persistent memory record)."""

    artifact_id: str
    title: str
    question: str
    answer: str
    provenance: Provenance = Provenance.SYSTEM
    review_status: str = ""
    content_hash: str = ""
    source_ids: tuple[str, ...] = ()
    acl_scope: str | None = None
    version: int = 1
    created_at: str = ""
    status: str = "active"


@dataclass(frozen=True)
class MemoryArtifactRef:
    """Lightweight deterministic recall reference for one artifact."""

    artifact_id: str
    title: str
    question: str
    answer: str  # empty when review-gated (pending/rejected)
    provenance: Provenance = Provenance.SYSTEM
    review_status: str = ""
    score: float = 0.0
    source_ids: tuple[str, ...] = ()
    version: int = 1
    created_at: str = ""


@dataclass(frozen=True)
class MemoryWriteCommand:
    """The write command for a memory artifact.

    ``provenance`` selects user-authored (ASSERTED) vs system/AI-derived
    (INFERRED/SYSTEM). ``acl`` lists grant the owner read/write by default so
    the artifact is isolated to the creating principal unless expanded.
    """

    question: str
    answer: str
    provenance: Provenance = Provenance.SYSTEM
    source_ids: tuple[str, ...] = ()
    readers: tuple[str, ...] = ()
    writers: tuple[str, ...] = ()
    managers: tuple[str, ...] = ()
    title: str | None = None


@dataclass(frozen=True)
class MemoryRecallResult:
    """Deterministic, ACL-filtered recall of persistent memory artifacts."""

    artifacts: tuple[MemoryArtifactRef, ...] = ()
    count: int = 0


__all__ = [
    "KEY_MEMORY_ANSWER",
    "KEY_MEMORY_CONTENT_HASH",
    "KEY_MEMORY_PROVENANCE",
    "KEY_MEMORY_QUESTION",
    "KEY_MEMORY_REVIEW_STATUS",
    "KEY_MEMORY_SOURCE_IDS",
    "REVIEW_APPROVED",
    "REVIEW_PENDING",
    "REVIEW_REJECTED",
    "MemoryArtifact",
    "MemoryArtifactRef",
    "MemoryRecallResult",
    "MemoryWriteCommand",
    "_REVIEW_VALUES",
]
