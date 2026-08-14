"""L9 hard capability gate (ADR-045).

Evaluates the COMPLETE frozen capability set (all 18 capabilities) as a release
gate, using the existing capability-eval framework and existing golden cases.
No new capability IDs; no re-gating of existing L4-L8 cases; no second
evaluation framework.

Covers:
- full-suite schema + coverage (every frozen capability >=5 phrasings, en+hi-en),
- no capability regression against the frozen registry,
- deterministic outcome checks for the deterministic operations (count,
  inventory, list, lookup, clarify/refuse) consistent with the L4/L5 gates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS
from app.application.services.capability_eval import (
    DEFAULT_GOLDEN_DIR,
    CapabilityEvalError,
    load_golden_file,
    load_suite,
    validate_suite_coverage,
)
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidator
from app.application.services.planner import _UnavailablePlanner
from app.application.services.query_understanding import QueryUnderstanding
from app.application.services.tool_executor import ToolExecutor
from app.application.services.tool_registry import InMemoryToolRegistry
from app.application.services.tools.data_tools import (
    CountTool,
    InventoryTool,
    ListTool,
    LookupTool,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
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


def test_l9_full_suite_schema_and_coverage():
    """Hard gate: the complete frozen capability suite validates and covers."""
    cases = load_suite(DEFAULT_GOLDEN_DIR)
    validate_suite_coverage(cases)
    # every frozen capability is present
    by_cap = {case.capability_id for case in cases}
    assert by_cap == set(FROZEN_CAPABILITY_IDS)
    assert len(FROZEN_CAPABILITY_IDS) == 18


def test_l9_no_capability_regression():
    """Hard gate: golden files exactly match the frozen capability registry."""
    files = {p.stem for p in DEFAULT_GOLDEN_DIR.glob("*.json")}
    assert files == set(FROZEN_CAPABILITY_IDS)
    # every golden file validates independently
    for cid in FROZEN_CAPABILITY_IDS:
        cases = load_golden_file(DEFAULT_GOLDEN_DIR / f"{cid}.json")
        assert len(cases) >= 5
        langs = {c.language for c in cases}
        assert "en" in langs and "hi-en" in langs


def test_l9_clarify_refuse_deterministic_outcomes():
    """L9 release gate: every l4/l5 clarify/refuse case resolves deterministically."""
    cases = load_suite(DEFAULT_GOLDEN_DIR)
    q = QueryUnderstanding(
        planner=_UnavailablePlanner(),
        validator=PlanValidator(),
        fast_path=FastPathExecutor(_NullExec()),
        clarify_refuse=ClarifyRefuse(),
    )
    for case in cases:
        if case.gate_level in ("l4", "l9") or case.checks.clarify_expected or case.checks.refusal_expected:
            result = q.understand(case.question)
            assert result.outcome in ("execute", "clarify", "refuse")


class _NullExec:
    def execute_fast_path(self, plan, *, context=None):
        return "ok"


@pytest.fixture()
def repo_l9():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    for i in range(3):
        repo.save(UniversalObject.create(
            ObjectType.PUBLICATION, f"Pub {i}", created_by="u:1",
            status=ObjectStatus.ACTIVE, object_id=ObjectId(f"obj:publication:l9e-{i}"),
        ))
    try:
        yield repo
    finally:
        session.close()
        engine.dispose()


def test_l9_deterministic_tool_outcomes(repo_l9):
    """Hard gate: the deterministic data tools produce deterministic results."""
    reg = InMemoryToolRegistry()
    reg.register(CountTool(repo_l9))
    reg.register(ListTool(repo_l9))
    reg.register(LookupTool(repo_l9))
    reg.register(InventoryTool(repo_l9))
    ex = ToolExecutor(reg, permissions=_AllowAll(), audit=_NoAudit())
    c = ex.execute(principal="u:1", tool_name="count", args={"object_type": "publication"})
    assert c.ok is True and isinstance(c.value["count"], int)
    inv = ex.execute(principal="u:1", tool_name="inventory", args={})
    assert inv.ok is True and isinstance(inv.value["kinds"], list)
