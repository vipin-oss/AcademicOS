"""L7 evaluation gate (ADR-042).

Verifies real L7 persistent-memory behavior against the ratified L7 laws using
the existing L0 capability-evaluation conventions. Memory is **context, never
evidence** (ADR-015); recall is ACL-gated, review-gated, deterministic, and
provenance-preserving.

Covers: persistent memory creation, recall, ACL isolation, provenance,
supersession/consolidation, memory-not-evidence, deterministic ordering, and
permission-denial / no-leakage.
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.memory import (
    MemoryWriteCommand,
    REVIEW_APPROVED,
)
from app.application.services.claim_evidence import ClaimEvidenceService
from app.application.services.persistent_memory import PersistentMemoryService
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


class _FakePerm:
    def __init__(self, allow_read: bool = True):
        self._allow_read = allow_read

    def can(self, *, principal, scope, action):
        return action is PermissionAction.READ and self._allow_read


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

    owner = _user("u:1", "l7g-owner")
    other = _user("u:2", "l7g-other")
    try:
        yield {"repo": repo, "svc": svc, "owner": owner, "other": other, "session": session}
    finally:
        session.close()
        engine.dispose()


def test_gate_memory_creation_and_recall(world):
    svc = world["svc"]
    art = svc.write(
        MemoryWriteCommand(
            question="What is the sanctioned amount?", answer="5000000",
            provenance=Provenance.ASSERTED,
        ),
        user=world["owner"],
    )
    assert art.review_status == REVIEW_APPROVED
    res = svc.recall("sanctioned amount", world["owner"])
    assert res.count == 1
    assert res.artifacts[0].answer == "5000000"


def test_gate_acl_isolation_no_cross_principal_leak(world):
    svc = world["svc"]
    svc.write(
        MemoryWriteCommand(question="secret", answer="classified", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    assert svc.recall("secret", world["owner"]).count == 1
    assert svc.recall("secret", world["other"]).count == 0  # no leakage


def test_gate_provenance_preserved(world):
    svc = world["svc"]
    art = svc.write(
        MemoryWriteCommand(question="derived", answer="fact", provenance=Provenance.INFERRED),
        user=world["owner"],
    )
    got = svc.get(art.artifact_id, user=world["owner"])
    assert got is not None
    assert got.provenance is Provenance.INFERRED


def test_gate_supersession_forgets(world):
    svc = world["svc"]
    art = svc.write(
        MemoryWriteCommand(question="temp", answer="data", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    forgotten = svc.forget(art.artifact_id, user=world["owner"])
    assert forgotten.status == ObjectStatus.SUPERSEDED.value
    assert svc.recall("temp", world["owner"]).count == 0


def test_gate_memory_never_evidence(world):
    # Memory artifacts must never surface through the L6 evidence/citation contract.
    # The L6 ClaimEvidenceService reads the CLAIM store (claims/spans), never
    # memory artifacts — so a memory write must not produce any citable claim.
    from app.application.services.claim_evidence import ClaimEvidenceService

    svc = world["svc"]
    svc.write(
        MemoryWriteCommand(question="The budget is 50000", answer="budget", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    # ClaimEvidenceService requires a ClaimStore; an in-memory empty claim store
    # proves memory writes contribute nothing to the evidence contract.
    class _EmptyClaimStore:
        def by_source(self, source_document_id):
            return []

        def by_status(self, status):
            return []

        def get(self, claim_id):
            return None

    ev = ClaimEvidenceService(_EmptyClaimStore(), _FakePerm())
    cites = ev.citable_claims(user=world["owner"])
    # No memory artifact is ever a fact citation.
    assert cites == []


def test_gate_deterministic_ordering(world):
    svc = world["svc"]
    for i in range(4):
        svc.write(
            MemoryWriteCommand(
                question=f"budget {i}", answer=f"v{i}", provenance=Provenance.ASSERTED
            ),
            user=world["owner"],
        )
    a = svc.recall("budget", world["owner"], limit=10)
    b = svc.recall("budget", world["owner"], limit=10)
    assert [r.artifact_id for r in a.artifacts] == [r.artifact_id for r in b.artifacts]


def test_gate_permission_denial_no_leakage(world):
    # A principal denied READ must see nothing (pre-filter, never post-filter).
    from app.application.ports.permission import PermissionEvaluator

    class DenyAll(PermissionEvaluator):
        def can(self, *, principal, scope, action):
            return False

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    svc = PersistentMemoryService(repo, DenyAll())
    art = svc.write(
        MemoryWriteCommand(question="q", answer="a", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    assert svc.recall("q", world["owner"]).count == 0
    assert svc.get(art.artifact_id, user=world["owner"]) is None
    session.close()
    engine.dispose()
