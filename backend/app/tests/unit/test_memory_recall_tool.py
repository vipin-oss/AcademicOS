"""L7 tests — the memory-recall L5 tool (Freeze Contract §18, ADR-041)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.memory import MemoryWriteCommand
from app.application.dtos.tool import ToolResult
from app.application.services.persistent_memory import PersistentMemoryService
from app.application.services.tool_executor import ToolExecutor
from app.application.services.tool_registry import InMemoryToolRegistry
from app.application.services.tools.memory_recall_tool import MemoryRecallTool
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
    # seed a USER object matching the tool's principal
    user = UniversalObject.create(
        ObjectType.USER, "u:1", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:l7t-1"),
    )
    repo.save(user)
    svc = PersistentMemoryService(repo, ObjectPermissionEvaluator())
    try:
        yield {"repo": repo, "svc": svc, "user": user}
    finally:
        session.close()
        engine.dispose()


def test_memory_recall_tool_returns_memories(world):
    world["svc"].write(
        MemoryWriteCommand(
            question="What is the budget?", answer="5000000", provenance=Provenance.ASSERTED
        ),
        user=world["user"],
    )
    tool = MemoryRecallTool(world["repo"], world["svc"])
    r = tool.execute(principal="u:1", args={"q": "budget", "limit": 5})
    assert r.ok is True
    assert r.value["count"] == 1
    assert r.value["artifacts"][0]["answer"] == "5000000"


def test_memory_recall_tool_unknown_principal_fails(world):
    tool = MemoryRecallTool(world["repo"], world["svc"])
    r = tool.execute(principal="u:does-not-exist", args={"q": "budget"})
    assert r.ok is False
    assert "Unknown principal" in (r.error or "")


def test_memory_recall_tool_runs_through_executor(world):
    world["svc"].write(
        MemoryWriteCommand(question="note", answer="data", provenance=Provenance.ASSERTED),
        user=world["user"],
    )
    reg = InMemoryToolRegistry()
    reg.register(MemoryRecallTool(world["repo"], world["svc"]))
    ex = ToolExecutor(reg, permissions=_AllowAll(), audit=_NoAudit())
    r = ex.execute(principal="u:1", tool_name="memory-recall", args={"q": "note"})
    assert r.ok is True
    assert r.value["count"] == 1


def test_registry_includes_memory_recall_tool(world):
    from app.application.services.tools.registry import build_tool_registry

    reg = build_tool_registry(world["repo"], memory=world["svc"])
    assert "memory-recall" in reg.names()
    # backward compatible: without memory, the tool is absent
    reg2 = build_tool_registry(world["repo"])
    assert "memory-recall" not in reg2.names()
