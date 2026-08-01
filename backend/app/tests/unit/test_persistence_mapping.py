"""Unit tests for the Persistence Mapping Layer.

Verifies: (1) snapshots are serializable to JSON, (2) the SnapshotMapper is
lossless for Domain -> Snapshot -> Domain, and (3) edge cases (empty
collections). No DB, no framework — pure conversion tests.
"""
from __future__ import annotations

import json

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.relationship import Relationship
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.snapshots import ObjectSnapshot


def _make_object() -> UniversalObject:
    obj = UniversalObject.create(
        ObjectType.RESEARCH_PROJECT,
        "Graph Neural Networks",
        created_by="faculty:7",
        status=ObjectStatus.ACTIVE,
    )
    obj.set_metadata(
        MetadataEntry("grant_id", "G-123", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        actor="faculty:7",
    )
    obj.set_metadata(
        MetadataEntry("topic", "gnn", MetadataLayer.L5_INFERRED, Provenance.INFERRED, confidence=0.82),
        actor="ai",
    )
    obj.add_relationship(
        ObjectId.generate(ObjectType.FACULTY), RelationshipKind.LEADS, Provenance.ASSERTED
    )
    obj.add_relationship(
        ObjectId.generate(ObjectType.PUBLICATION),
        RelationshipKind.PRODUCES,
        Provenance.INFERRED,
        confidence=0.7,
        evidence=("fig 2", "sec 3"),
        acl_scope="space:ai",
    )
    obj.change_status(ObjectStatus.ARCHIVED, "faculty:7")
    obj.pop_domain_events()  # mimic post-persist outbox drain
    return obj


def test_snapshot_is_json_serializable():
    obj = _make_object()
    snap = SnapshotMapper.to_snapshot(obj)
    payload = json.dumps(snap.to_dict())  # must not raise
    data = json.loads(payload)
    assert data["object_type"] == "research_project"
    assert data["status"] == "archived"
    assert data["metadata"][0]["layer"] == 6
    assert data["relationships"][1]["evidence"] == ["fig 2", "sec 3"]
    assert isinstance(data["audit"]["created_at"], str)


def test_mapper_roundtrip_is_lossless():
    obj = _make_object()
    snap1 = SnapshotMapper.to_snapshot(obj)

    # Domain -> Snapshot -> Domain -> Snapshot must be identical
    obj2 = SnapshotMapper.from_snapshot(snap1)
    snap2 = SnapshotMapper.to_snapshot(obj2)
    assert snap1 == snap2

    # Explicit field fidelity
    assert obj2.id == obj.id
    assert obj2.object_type == obj.object_type
    assert obj2.title == obj.title
    assert obj2.status == obj.status
    assert obj2.version == obj.version

    assert len(obj2.metadata.entries) == 2
    by_key = {e.key: e for e in obj2.metadata.entries}
    assert by_key["grant_id"].value == "G-123"
    assert by_key["grant_id"].source is Provenance.ASSERTED
    assert by_key["topic"].confidence == 0.82

    assert len(obj2.relationships) == 2
    r0, r1 = obj2.relationships[0], obj2.relationships[1]
    assert r0.kind == RelationshipKind.LEADS
    assert r1.kind == RelationshipKind.PRODUCES
    assert r1.confidence == 0.7
    assert tuple(r1.evidence) == ("fig 2", "sec 3")
    assert r1.acl_scope == "space:ai"

    assert obj2.audit is not None
    assert obj2.audit.created_by == "faculty:7"
    assert obj2.audit.updated_by == "faculty:7"


def test_empty_collections_roundtrip():
    obj = UniversalObject.create(
        ObjectType.COURSE, "Intro to CS", created_by="faculty:2"
    )
    obj.pop_domain_events()
    snap = SnapshotMapper.to_snapshot(obj)
    assert snap.metadata == ()
    assert snap.relationships == ()
    obj2 = SnapshotMapper.from_snapshot(snap)
    snap2 = SnapshotMapper.to_snapshot(obj2)
    assert snap == snap2
    assert obj2.title == "Intro to CS"


def test_snapshot_type():
    obj = _make_object()
    snap = SnapshotMapper.to_snapshot(obj)
    assert isinstance(snap, ObjectSnapshot)
    assert snap.to_json().startswith("{")
