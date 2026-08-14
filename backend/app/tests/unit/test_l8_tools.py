"""L8 tests — the four cross-domain L5 tools via the existing executor seam."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cross_domain import CrossDomainService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.tool_executor import ToolExecutor
from app.application.services.tool_registry import InMemoryToolRegistry
from app.application.services.tools.absence_tool import AbsenceTool
from app.application.services.tools.compare_tool import CompareTool
from app.application.services.tools.cross_domain_tool import CrossDomainTool
from app.application.services.tools.temporal_tool import TemporalTool
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
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


class _AllowAll:
    def can(self, *, principal, scope, action):
        return action is PermissionAction.READ


class _NoAudit:
    def add(self, record):
        return record

    def recent(self, limit=50):
        return []


@pytest.fixture()
def world():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    user = UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l8t-1"),
    )
    repo.save(user)
    grant = UniversalObject.create(
        ObjectType.GRANT, "HSRF Grant", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:grant:l8t-1"),
    )
    pub = UniversalObject.create(
        ObjectType.PUBLICATION, "Catalyst Paper", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:publication:l8t-1"),
    )
    repo.save(grant)
    repo.save(pub)
    grant.add_relationship(pub.id, RelationshipKind.PRODUCES, actor="system")
    repo.save(grant)
    svc = CrossDomainService(repo, GraphRuntimeService(repo, ObjectPermissionEvaluator()), ObjectPermissionEvaluator())
    try:
        yield {"repo": repo, "svc": svc, "user": user, "grant": grant, "pub": pub}
    finally:
        session.close()
        engine.dispose()


def _registry(world):
    reg = InMemoryToolRegistry()
    reg.register(CrossDomainTool(world["repo"], world["svc"]))
    reg.register(AbsenceTool(world["repo"], world["svc"]))
    reg.register(TemporalTool(world["repo"], world["svc"]))
    reg.register(CompareTool(world["repo"], world["svc"]))
    return reg


def _executor(world):
    return ToolExecutor(_registry(world), permissions=_AllowAll(), audit=_NoAudit())


def test_tools_run_through_executor(world):
    ex = _executor(world)
    r = ex.execute(principal="u:1", tool_name="cross-domain", args={"entities": [str(world["grant"].id)], "depth": 2})
    assert r.ok is True
    assert r.value["total_count"] >= 2


def test_absence_tool_through_executor(world):
    ex = _executor(world)
    r = ex.execute(principal="u:1", tool_name="absence", args={"object_type": "course"})
    assert r.ok is True
    assert r.value["outcome"] in ("confirmed_absence", "present", "insufficient_evidence")


def test_temporal_tool_through_executor(world):
    ex = _executor(world)
    r = ex.execute(principal="u:1", tool_name="temporal", args={"time_range": "this year", "object_type": "publication"})
    assert r.ok is True
    assert r.value["count"] >= 1  # publications created this year


def test_compare_tool_through_executor(world):
    ex = _executor(world)
    r = ex.execute(principal="u:1", tool_name="compare", args={"labels": [str(world["grant"].id), "missing"], "object_type": "grant"})
    assert r.ok is True
    rows = {x["label"]: x for x in r.value["rows"]}
    assert rows["missing"]["missing"] is True


def test_registry_includes_l8_tools(world):
    from app.application.services.tools.registry import build_tool_registry

    reg = build_tool_registry(world["repo"], cross_domain=world["svc"])
    for name in ("cross-domain", "absence", "temporal", "compare"):
        assert name in reg.names()
    # backward compatible: without cross_domain the tools are absent
    reg2 = build_tool_registry(world["repo"])
    for name in ("cross-domain", "absence", "temporal", "compare"):
        assert name not in reg2.names()
