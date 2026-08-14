"""L7 persistent memory service (ADR-041).

The single durable memory seam over the existing ``ObjectRepository`` +
``UniversalObject`` (object_type ``memory_artifact``). No new table, no migration
— memory lives as metadata on the existing ``objects`` table.

Persistence + lifecycle:
- create a ``UniversalObject`` with object_type ``memory_artifact``; payload is
  stored as L1_SYSTEM metadata (question/answer/content_hash/source_ids/
  review_status/provenance).
- provenance selects the write: user-authored ``ASSERTED`` artifacts default to
  ``approved`` (trusted); system/AI ``INFERRED``/``SYSTEM`` artifacts default to
  ``pending`` and are review-gated before recall.
- ``forget`` marks the artifact SUPERSEDED via ``UniversalObject.supersede`` (no
  delete); SUPERSEDED artifacts are excluded from recall.
- ACL: the artifact carries object-level ACL metadata; every read is pre-filtered
  through the existing ``PermissionEvaluator`` (``object_acl_scope``).

Security / determinism:
- recall is ACL-gated (pre-filter, never post-filter) and review-gated
  (pending/rejected content returns an empty answer).
- ordering is deterministic (relevance score desc, then artifact id asc).
- memory is context, never evidence (ADR-015): this service never feeds the L6
  citation/evidence contract.

Reuses: ``ObjectRepository``, ``UniversalObject``/``ObjectId``, ``object_acl_scope``,
``PermissionEvaluator``, ``MetadataEntry``/``MetadataLayer``/``Provenance``.
Does NOT create a second memory store, retrieval system, or ACL system.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.application.dtos.memory import (
    KEY_MEMORY_ANSWER,
    KEY_MEMORY_CONTENT_HASH,
    KEY_MEMORY_PROVENANCE,
    KEY_MEMORY_QUESTION,
    KEY_MEMORY_REVIEW_STATUS,
    KEY_MEMORY_SOURCE_IDS,
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    MemoryArtifact,
    MemoryArtifactRef,
    MemoryRecallResult,
    MemoryWriteCommand,
    _REVIEW_VALUES,
)
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    PermissionAction,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

#: ACL metadata keys (mirror app.application.dtos.object).
ACL_OWNER = "acl.owner"
ACL_READERS = "acl.readers"
ACL_WRITERS = "acl.writers"
ACL_MANAGERS = "acl.managers"

#: A user-authored artifact is trusted immediately (approved); system/AI-derived
#: artifacts are pending until review.
_ASSERTED_REVIEW = REVIEW_APPROVED
_INFERRED_REVIEW = REVIEW_PENDING
_SYSTEM_REVIEW = REVIEW_PENDING


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").casefold()))


def content_hash(question: str, answer: str) -> str:
    """Deterministic content hash of a memory artifact's payload."""
    return hashlib.sha256(
        f"{question.strip().casefold()}\x00{answer.strip().casefold()}".encode("utf-8")
    ).hexdigest()


class PersistentMemoryService:
    """Durable memory artifacts over the existing object store (ADR-041)."""

    def __init__(
        self,
        repository: ObjectRepository,
        permissions: PermissionEvaluator,
    ) -> None:
        self._repository = repository
        self._permissions = permissions

    # ------------------------------------------------------------------ write
    def write(
        self, command: MemoryWriteCommand, *, user: UniversalObject
    ) -> MemoryArtifact:
        """Persist one memory artifact authored by ``user``."""
        if not command.question.strip() and not command.answer.strip():
            raise ValueError("Memory artifact must carry a question or answer.")

        h = content_hash(command.question, command.answer)
        owner = str(user.id)
        readers = tuple(command.readers) or (owner,)
        writers = tuple(command.writers) or (owner,)
        managers = tuple(command.managers) or (owner,)

        obj = UniversalObject.create(
            object_type=ObjectType.MEMORY_ARTIFACT,
            title=command.title or _default_title(command.question),
            created_by=owner,
            status=ObjectStatus.ACTIVE,
        )

        review_status = _review_for(command.provenance)
        self._set(obj, KEY_MEMORY_QUESTION, command.question, Provenance.SYSTEM)
        self._set(obj, KEY_MEMORY_ANSWER, command.answer, Provenance.SYSTEM)
        self._set(obj, KEY_MEMORY_CONTENT_HASH, h, Provenance.SYSTEM)
        self._set(
            obj, KEY_MEMORY_SOURCE_IDS, json.dumps(list(command.source_ids)), Provenance.SYSTEM
        )
        self._set(obj, KEY_MEMORY_REVIEW_STATUS, review_status, Provenance.SYSTEM)
        self._set(obj, KEY_MEMORY_PROVENANCE, command.provenance.value, command.provenance)
        # ACL metadata (isolated to owner by default).
        self._set_acl(obj, owner, readers, writers, managers, command.provenance)

        self._repository.save(obj)
        return self._to_artifact(obj)

    # ------------------------------------------------------------------ recall
    def recall(
        self, query: str, user: UniversalObject, *, limit: int = 10
    ) -> MemoryRecallResult:
        """ACL-visible, review-approved memory artifacts for ``query``.

        Deterministic order: relevance (query-token overlap on question+answer)
        desc, then artifact id asc. Pending/rejected artifacts are recalled with
        an empty answer (review gate).
        """
        artifacts = self._recall_candidates(user, limit=limit)
        scored: list[tuple[float, str, MemoryArtifact]] = []
        q_tokens = _tokens(query)
        for art in artifacts:
            body = _tokens(art.question) | _tokens(art.answer)
            score = float(len(q_tokens & body)) if q_tokens else 0.0
            scored.append((score, art.artifact_id, art))
        # Deterministic: score desc, artifact id asc.
        scored.sort(key=lambda item: (-item[0], item[1]))
        refs = tuple(self._to_ref(art) for _s, _i, art in scored[:limit])
        return MemoryRecallResult(artifacts=refs, count=len(refs))

    def list(self, user: UniversalObject, *, limit: int = 100) -> MemoryRecallResult:
        """The principal's ACL-visible, review-approved artifacts, deterministic."""
        artifacts = self._recall_candidates(user, limit=limit)
        artifacts.sort(key=lambda a: (a.created_at, a.artifact_id))
        refs = tuple(self._to_ref(a) for a in artifacts[:limit])
        return MemoryRecallResult(artifacts=refs, count=len(refs))

    # ------------------------------------------------------------------ forget
    def forget(self, artifact_id: str, *, user: UniversalObject) -> MemoryArtifact:
        """Mark one artifact SUPERSEDED (no delete). Only the owner/manager may."""
        obj = self._repository.get_by_id(ObjectId(artifact_id))
        if obj is None or obj.object_type is not ObjectType.MEMORY_ARTIFACT:
            raise KeyError(f"Memory artifact not found: {artifact_id}")
        self._assert_can_forget(obj, user)
        obj.supersede(obj.id, str(user.id), at=datetime.now(UTC))
        self._repository.save(obj)
        return self._to_artifact(obj)

    # ------------------------------------------------------------------ get
    def get(self, artifact_id: str, *, user: UniversalObject) -> MemoryArtifact | None:
        obj = self._repository.get_by_id(ObjectId(artifact_id))
        if obj is None or obj.object_type is not ObjectType.MEMORY_ARTIFACT:
            return None
        if not self._can_read(obj, user):
            return None
        return self._to_artifact(obj)

    # ------------------------------------------------------------------ auth
    def _recall_candidates(
        self, user: UniversalObject, *, limit: int
    ) -> list[MemoryArtifact]:
        out: list[MemoryArtifact] = []
        for obj in self._repository.find(
            object_type=ObjectType.MEMORY_ARTIFACT,
            status=ObjectStatus.ACTIVE,
        ):
            if not self._can_read(obj, user):
                continue  # pre-filter — never leak
            out.append(self._to_artifact(obj))
            if len(out) >= limit:
                break
        return out

    def _can_read(self, obj: UniversalObject, user: UniversalObject) -> bool:
        return self._permissions.can(
            principal=_principal(user),
            scope=object_acl_scope(obj),
            action=PermissionAction.READ,
        )

    def _assert_can_forget(self, obj: UniversalObject, user: UniversalObject) -> None:
        if not self._permissions.can(
            principal=_principal(user),
            scope=object_acl_scope(obj),
            action=PermissionAction.MANAGE,
        ):
            raise PermissionError("Not authorized to forget this memory artifact")

    # ------------------------------------------------------------------ build
    def _to_artifact(self, obj: UniversalObject) -> MemoryArtifact:
        m = obj.metadata
        prov_raw = m.get_value(KEY_MEMORY_PROVENANCE)
        provenance = Provenance(prov_raw) if prov_raw in Provenance._value2member_map_ else Provenance.SYSTEM
        return MemoryArtifact(
            artifact_id=str(obj.id),
            title=obj.title,
            question=m.get_value(KEY_MEMORY_QUESTION) or "",
            answer=m.get_value(KEY_MEMORY_ANSWER) or "",
            provenance=provenance,
            review_status=m.get_value(KEY_MEMORY_REVIEW_STATUS) or "",
            content_hash=m.get_value(KEY_MEMORY_CONTENT_HASH) or "",
            source_ids=_load_json_list(m.get_value(KEY_MEMORY_SOURCE_IDS)),
            acl_scope=object_acl_scope(obj),
            version=obj.version,
            created_at=(obj.audit.created_at if obj.audit else ""),
            status=obj.status.value,
        )

    def _to_ref(self, art: MemoryArtifact) -> MemoryArtifactRef:
        # Review gate: pending/rejected content is recalled with an empty answer.
        visible = art.review_status in ("", REVIEW_APPROVED)
        return MemoryArtifactRef(
            artifact_id=art.artifact_id,
            title=art.title,
            question=art.question,
            answer=art.answer if visible else "",
            provenance=art.provenance,
            review_status=art.review_status,
            score=0.0,
            source_ids=art.source_ids,
            version=art.version,
            created_at=art.created_at,
        )

    # ------------------------------------------------------------------ meta
    def _set(
        self, obj: UniversalObject, key: str, value: str, provenance: Provenance
    ) -> None:
        obj.set_metadata(
            MetadataEntry(
                key,
                value,
                MetadataLayer.L1_SYSTEM,
                provenance,
            ),
            actor="system",
        )

    def _set_acl(
        self,
        obj: UniversalObject,
        owner: str,
        readers: tuple[str, ...],
        writers: tuple[str, ...],
        managers: tuple[str, ...],
        provenance: Provenance,
    ) -> None:
        for key, entries in (
            (ACL_OWNER, (owner,)),
            (ACL_READERS, readers),
            (ACL_WRITERS, writers),
            (ACL_MANAGERS, managers),
        ):
            self._set(obj, key, json.dumps(list(entries)), provenance)


def _principal(user: UniversalObject) -> dict:
    """The principal dict consumed by ``PermissionEvaluator`` (sub + roles)."""
    from app.application.use_cases.auth.helpers import get_roles

    return {"sub": str(user.id), "roles": get_roles(user)}


def _review_for(provenance: Provenance) -> str:
    if provenance is Provenance.ASSERTED:
        return _ASSERTED_REVIEW
    if provenance is Provenance.INFERRED:
        return _INFERRED_REVIEW
    return _SYSTEM_REVIEW


def _default_title(question: str) -> str:
    return (question.strip() or "Memory artifact")[:120]


def _load_json_list(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return ()
    return tuple(str(e) for e in parsed if isinstance(e, str))


def is_memory_artifact(obj: Any) -> bool:
    """True when an object is a durable memory artifact (helper/guardrail)."""
    return getattr(obj, "object_type", None) is ObjectType.MEMORY_ARTIFACT


__all__ = [
    "PersistentMemoryService",
    "content_hash",
    "is_memory_artifact",
]
