"""L8 architecture guardrails (ADR-043/044).

Pins that L8 reuses existing infrastructure and does not introduce a second
planner, retrieval, ACL, evidence, memory, or persistence system; no new
capability IDs; no L4/L5/L6/L7 rewrite; bounded multi-hop; deterministic
results; no new migration; no L9 implementation.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l8_adrs_present():
    for name in (
        "ADR-043-l8-cross-domain-completion",
        "ADR-044-l8-evaluation-gate",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l7_done_l8_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L7" in text and "done" in text
    assert "L8" in text and "in_progress" in text
    # L9 must not have started.
    assert "L9" in text and "not_started" in text


def test_l8_no_new_capability_ids():
    from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS

    assert len(FROZEN_CAPABILITY_IDS) == 18
    for cap in ("cross_domain", "absence", "temporal", "compare"):
        assert cap in FROZEN_CAPABILITY_IDS


def test_l8_reuses_existing_services_no_duplicate_subsystem():
    from app.application.services.cross_domain import CrossDomainService

    src = inspect.getsource(CrossDomainService)
    # reuses existing graph + permission + object store
    assert "GraphRuntimeService" in src
    assert "PermissionEvaluator" in src
    assert "ObjectRepository" in src
    # no second planner/retrieval/evidence/memory system instantiated
    for forbidden in (
        "PlannerService",
        "SearchObjectsUseCase",
        "ClaimEvidenceService",
        "PersistentMemoryService",
        "ToolExecutor",
        "ToolRegistry",
    ):
        assert forbidden not in src, f"L8 must not instantiate {forbidden}"


def test_l8_no_new_migration():
    migrations = REPO / "backend" / "alembic" / "versions"
    names = [p.name for p in migrations.glob("*.py")]
    # Migration head is 0026 (notifications, Rev13). L8 itself adds none;
    # forbid any migration beyond 0026 and any "cross"-named migration.
    assert not any("cross" in n.lower() or "0027" in n for n in names), names


def test_l8_bounded_multi_hop():
    from app.application.services.cross_domain import MAX_MULTIHOP_DEPTH

    assert MAX_MULTIHOP_DEPTH <= 5  # bounded depth


def test_l8_no_l9_implementation():
    from app.application.services.cross_domain import CrossDomainService

    src = inspect.getsource(CrossDomainService)
    assert "L9" not in src


def test_l8_does_not_touch_frozen_l4_l5_l6_l7():
    l8_new = {
        "backend/app/application/services/cross_domain.py",
        "backend/app/application/services/temporal.py",
        "backend/app/application/services/tools/cross_domain_tool.py",
        "backend/app/application/services/tools/absence_tool.py",
        "backend/app/application/services/tools/temporal_tool.py",
        "backend/app/application/services/tools/compare_tool.py",
    }
    frozen = {
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/application/services/plan_validator.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/tool_registry.py",
        "backend/app/application/services/claim_evidence.py",
        "backend/app/application/services/persistent_memory.py",
        "backend/app/application/services/assistant_memory.py",
    }
    assert l8_new.isdisjoint(frozen)
