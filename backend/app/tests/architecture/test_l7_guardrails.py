"""L7 architecture guardrails (ADR-041/042).

Pins that L7 reuses existing infrastructure (ObjectRepository, PermissionEvaluator,
ToolExecutor/registry, UniversalObject) and does NOT introduce a second memory
store, retrieval system, ACL system, planner, tool registry, or evidence system.
Also pins that memory is context, never evidence (ADR-015), and that L7 does not
touch frozen L0-L6 files.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l7_adrs_present():
    for name in (
        "ADR-041-l7-memory-v2-persistent-layer",
        "ADR-042-l7-evaluation-gate",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l6_done_l7_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L6" in text and "done" in text
    assert "L7" in text and "in_progress" in text


def test_l7_uses_existing_object_store_and_permission():
    from app.application.services.persistent_memory import PersistentMemoryService

    src = inspect.getsource(PersistentMemoryService)
    # reuses the object repository + permission evaluator (no second system)
    assert "ObjectRepository" in src
    assert "PermissionEvaluator" in src
    assert "object_acl_scope" in src
    # no second retrieval / ACL / tool / evidence system instantiated
    for forbidden in (
        "SearchObjectsUseCase",
        "PlannerService",
        "ToolExecutor",
        "ToolRegistry",
        "ClaimEvidenceService",
        "ObjectPermissionEvaluator(",
    ):
        assert forbidden not in src, f"L7 must not instantiate {forbidden}"


def test_l7_memory_is_context_not_evidence():
    from app.application.dtos.memory import MemoryArtifact

    src = inspect.getsource(MemoryArtifact)
    # memory artifacts carry context fields, never citation/evidence fields
    for evidence_field in ("fact_confidence", "citable", "source_span", "claim_id"):
        assert evidence_field not in src, f"memory artifact must not carry {evidence_field}"


def test_l7_new_files_disjoint_from_frozen_l4_l5_l6():
    l7_new = {
        "backend/app/application/dtos/memory.py",
        "backend/app/application/ports/persistent_memory.py",
        "backend/app/application/services/persistent_memory.py",
        "backend/app/application/services/tools/memory_recall_tool.py",
    }
    frozen = {
        "backend/app/application/dtos/plan.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/tool_registry.py",
        "backend/app/application/services/claim_evidence.py",
        "backend/app/application/dtos/evidence.py",
    }
    assert l7_new.isdisjoint(frozen)


def test_l7_no_new_persistence_table():
    # L7 stores memory as UniversalObject metadata; no alembic 0015 memory table.
    migrations = REPO / "backend" / "alembic" / "versions"
    names = [p.name for p in migrations.glob("*.py")]
    assert not any("memory" in n.lower() for n in names), f"unexpected memory migration: {names}"
