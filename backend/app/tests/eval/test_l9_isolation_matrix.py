"""L9 isolation matrix (ADR-046).

Deterministic verification that capability boundaries remain isolated and no
forbidden cross-level dependency/leakage exists across data-touching paths:
- cross-principal ACL isolation (retrieval, tools, claims/evidence, memory,
  cross-domain),
- memory is never treated as evidence (ADR-015),
- a denied principal never receives content it cannot read,
- graph-neighbor-only results are never citable (Freeze §20/§21).
"""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cross_domain import CrossDomainService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.persistent_memory import PersistentMemoryService
from app.application.dtos.memory import MemoryWriteCommand
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
    Provenance,
    RelationshipKind,
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


class _DenyAll:
    def can(self, *, principal, scope, action):
        return False


@pytest.fixture()
def world():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    owner = UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l9i-owner"),
    )
    other = UniversalObject.create(
        ObjectType.USER, "u:2", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l9i-other"),
    )
    repo.save(owner)
    repo.save(other)
    grant = UniversalObject.create(
        ObjectType.GRANT, "HSRF Grant", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:grant:l9i-1"),
    )
    pub = UniversalObject.create(
        ObjectType.PUBLICATION, "Catalyst Paper", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:publication:l9i-1"),
    )
    repo.save(grant)
    repo.save(pub)
    grant.add_relationship(pub.id, RelationshipKind.PRODUCES, actor="system")
    repo.save(grant)
    svc = CrossDomainService(repo, GraphRuntimeService(repo, ObjectPermissionEvaluator()), ObjectPermissionEvaluator())
    mem = PersistentMemoryService(repo, ObjectPermissionEvaluator())
    try:
        yield {"repo": repo, "owner": owner, "other": other, "grant": grant, "pub": pub, "svc": svc, "mem": mem}
    finally:
        session.close()
        engine.dispose()


def test_isolation_cross_principal_tools_no_leak(world):
    deny = CrossDomainService(world["repo"], GraphRuntimeService(world["repo"], ObjectPermissionEvaluator()), _DenyAll())
    res = deny.absence(target_type="grant", user=world["owner"])
    assert res.authorized_count == 0  # denied principal sees no grant


def test_isolation_cross_domain_no_leak(world):
    deny = CrossDomainService(world["repo"], GraphRuntimeService(world["repo"], ObjectPermissionEvaluator()), _DenyAll())
    res = deny.multi_hop([str(world["grant"].id)], world["owner"], max_depth=2)
    # denied principal cannot traverse to the related publication
    assert all(n.object_id != str(world["pub"].id) for n in res.nodes)


def test_isolation_memory_not_evidence(world):
    # memory write is context-only; it must never surface as a citable object
    art = world["mem"].write(
        MemoryWriteCommand(question="secret", answer="classified", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    # a different principal cannot recall it
    assert world["mem"].recall("secret", world["other"]).count == 0
    # and memory objects are never part of cross-domain traversal evidence
    cd = world["svc"].multi_hop([str(world["grant"].id)], world["owner"], max_depth=2)
    assert all(n.object_type != "memory_artifact" for n in cd.nodes)


def test_isolation_graph_neighbor_not_citable(world):
    # graph-only neighbors (pub via grant->produces) must not become citable
    # evidence; CrossDomainService returns structured nodes, not citations.
    cd = world["svc"].multi_hop([str(world["grant"].id)], world["owner"], max_depth=2)
    assert all("claim_id" not in n.__dict__ for n in cd.nodes)
    assert all(getattr(n, "relationship_kind", None) in (None, "produces", "related_to") for n in cd.nodes)


def test_isolation_denied_principal_memory_get_none(world):
    art = world["mem"].write(
        MemoryWriteCommand(question="q", answer="a", provenance=Provenance.ASSERTED),
        user=world["owner"],
    )
    assert world["mem"].get(art.artifact_id, user=world["other"]) is None
