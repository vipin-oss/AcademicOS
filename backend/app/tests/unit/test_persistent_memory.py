"""L7 unit tests — persistent memory service (ADR-041)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.memory import (
    MemoryWriteCommand,
    REVIEW_APPROVED,
    REVIEW_PENDING,
)
from app.application.services.persistent_memory import (
    PersistentMemoryService,
    content_hash,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
    Provenance,
)
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


@pytest.fixture()
def world():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    svc = PersistentMemoryService(repo, ObjectPermissionEvaluator())

    def _user(id: str, suffix: str) -> UniversalObject:
        return UniversalObject.create(
            ObjectType.USER, id, created_by="system", status=ObjectStatus.ACTIVE,
            object_id=ObjectId(f"obj:user:{suffix}"),
        )

    owner = _user("u:1", "l7-owner")
    other = _user("u:2", "l7-other")
    try:
        yield {"repo": repo, "svc": svc, "owner": owner, "other": other, "session": session}
    finally:
        session.close()
        engine.dispose()


def test_content_hash_deterministic():
    assert content_hash("What is the budget?", "50000") == content_hash("What is the budget?", "50000")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_write_system_memory_is_pending_review_gated(world):
    art = world["svc"].write(
        MemoryWriteCommand(question="What is the budget?", answer="50000"),
        user=world["owner"],
    )
    assert art.review_status == REVIEW_PENDING  # system-derived, pending
    assert art.provenance is Provenance.SYSTEM
    assert content_hash("What is the budget?", "50000") == art.content_hash
    # pending -> empty answer on recall (review gate)
    res = world["svc"].recall("budget", world["owner"])
    assert res.count == 1
    assert res.artifacts[0].answer == ""


def test_write_user_asserted_memory_is_approved_and_recallable(world):
    art = world["svc"].write(
        MemoryWriteCommand(
            question="My note", answer="remember this", provenance=Provenance.ASSERTED
        ),
        user=world["owner"],
    )
    assert art.review_status == REVIEW_APPROVED
    res = world["svc"].recall("note", world["owner"])
    assert res.count == 1
    assert res.artifacts[0].answer == "remember this"


def test_acl_isolation_no_leakage(world):
    art = world["svc"].write(
        MemoryWriteCommand(question="secret", answer="classified", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    assert world["svc"].recall("secret", world["owner"]).count == 1
    assert world["svc"].recall("secret", world["other"]).count == 0
    assert world["svc"].get(art.artifact_id, user=world["other"]) is None
    with pytest.raises(PermissionError):
        world["svc"].forget(art.artifact_id, user=world["other"])


def test_forget_marks_superseded_and_excludes_from_recall(world):
    art = world["svc"].write(
        MemoryWriteCommand(question="temp", answer="data", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    forgotten = world["svc"].forget(art.artifact_id, user=world["owner"])
    assert forgotten.status == ObjectStatus.SUPERSEDED.value
    assert world["svc"].recall("temp", world["owner"]).count == 0


def test_provenance_preserved(world):
    art = world["svc"].write(
        MemoryWriteCommand(question="q", answer="a", provenance=Provenance.INFERRED),
        user=world["owner"],
    )
    got = world["svc"].get(art.artifact_id, user=world["owner"])
    assert got is not None
    assert got.provenance is Provenance.INFERRED


def test_deterministic_ordering_and_bounded_limit(world):
    svc = world["svc"]
    owner = world["owner"]
    for i in range(5):
        svc.write(
            MemoryWriteCommand(
                question=f"budget line {i}", answer=f"value {i}",
                provenance=Provenance.ASSERTED,
            ),
            user=owner,
        )
    a = svc.recall("budget", owner, limit=3)
    b = svc.recall("budget", owner, limit=3)
    assert [r.artifact_id for r in a.artifacts] == [r.artifact_id for r in b.artifacts]
    assert len(a.artifacts) == 3  # bounded


def test_review_gate_rejected_content_not_recalled(world):
    svc = world["svc"]
    owner = world["owner"]
    # reject path: set review status to rejected directly (simulate review)
    art = svc.write(
        MemoryWriteCommand(question="x", answer="y", provenance=Provenance.SYSTEM),
        user=owner,
    )
    obj = world["repo"].get_by_id(ObjectId(art.artifact_id))
    from app.application.dtos.memory import KEY_MEMORY_REVIEW_STATUS, REVIEW_REJECTED
    from app.domain.value_objects.metadata import MetadataEntry
    from app.domain.value_objects.enums import MetadataLayer

    obj.set_metadata(
        MetadataEntry(KEY_MEMORY_REVIEW_STATUS, REVIEW_REJECTED, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
        actor="system",
    )
    world["repo"].save(obj)
    res = svc.recall("x", owner)
    # still recalled as a record, but content gated empty (review gate)
    assert res.count == 1
    assert res.artifacts[0].answer == ""
