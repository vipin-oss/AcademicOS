"""Snapshot structures for persistence mapping.

A *snapshot* is the serializable, framework-free shape of a Domain object. Every
field is a JSON primitive (str/int/float/bool/None/list/dict) so the snapshot
can be dumped to JSON and later handed to any persistence technology (SQL,
document store, Qdrant, event log) without coupling the Domain to it.

Enums are stored by their value; datetimes by their ISO-8601 string. The
``SnapshotMapper`` converts these back to live Domain objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetadataSnapshot:
    key: str
    value: str
    layer: int
    source: str  # Provenance value
    confidence: float | None = None
    recorded_at: str = ""  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "layer": self.layer,
            "source": self.source,
            "confidence": self.confidence,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class RelationshipSnapshot:
    target: str  # ObjectId value
    kind: str  # RelationshipKind value
    provenance: str  # Provenance value
    confidence: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    acl_scope: str | None = None
    created_at: str = ""  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "kind": self.kind,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "acl_scope": self.acl_scope,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AuditSnapshot:
    created_by: str
    created_at: str  # ISO-8601
    updated_by: str | None = None
    updated_at: str | None = None  # ISO-8601 or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ObjectSnapshot:
    id: str  # ObjectId value
    object_type: str  # ObjectType value
    title: str
    status: str  # ObjectStatus value
    version: int
    metadata: tuple[MetadataSnapshot, ...] = field(default_factory=tuple)
    relationships: tuple[RelationshipSnapshot, ...] = field(default_factory=tuple)
    audit: AuditSnapshot | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object_type": self.object_type,
            "title": self.title,
            "status": self.status,
            "version": self.version,
            "metadata": [m.to_dict() for m in self.metadata],
            "relationships": [r.to_dict() for r in self.relationships],
            "audit": self.audit.to_dict() if self.audit else None,
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False)


def object_snapshot_from_dict(data: dict) -> ObjectSnapshot:
    """Reconstruct an ``ObjectSnapshot`` from its ``to_dict()`` form.

    The inverse of ``ObjectSnapshot.to_dict()``, used to lift stored
    version-snapshot rows back into snapshot shape (Sprint-5 M1 — search
    documents are rebuilt entirely from version snapshots). The stored
    dict is the exact ``to_dict()`` output, so every field round-trips.
    """
    return ObjectSnapshot(
        id=str(data["id"]),
        object_type=str(data["object_type"]),
        title=str(data["title"]),
        status=str(data["status"]),
        version=int(data["version"]),
        metadata=tuple(MetadataSnapshot(**m) for m in data["metadata"]),
        relationships=tuple(RelationshipSnapshot(**r) for r in data["relationships"]),
        audit=AuditSnapshot(**data["audit"]) if data.get("audit") else None,
    )
