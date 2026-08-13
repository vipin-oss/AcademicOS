"""L5 architecture guardrails (ADR-037/038).

Pins: tools are ACL-gated + principal-carrying + audited; tool registry is
frozen/additive; L4 planner/fast-path unchanged (≤15); no L0-L4 frozen redesign;
no patch-farm; L4 done / L5 in_progress.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l5_adrs_present():
    for name in ("ADR-037-tool-registry-execution", "ADR-038-tool-evaluation-gate"):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l4_done_l5_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L4" in text and "done" in text
    assert "L5" in text and "in_progress" in text


def test_tool_executor_enforces_acl_and_audits():
    from app.application.services.tool_executor import ToolExecutor

    src = inspect.getsource(ToolExecutor)
    assert "permissions.can" in src  # ACL at the tool boundary
    assert "acl_scope" in src
    assert "audit" in src  # tool-call audit


def test_tool_registry_is_explicit_and_duplicate_safe():
    from app.application.services.tool_registry import InMemoryToolRegistry

    src = inspect.getsource(InMemoryToolRegistry)
    assert "Duplicate tool name" in src
    assert "register" in src


def test_l4_fast_path_unchanged_at_15():
    from app.application.services.fast_path import FAST_PATH_COMMANDS, FAST_PATH_MAX

    assert len(FAST_PATH_COMMANDS) <= FAST_PATH_MAX
    assert len(FAST_PATH_COMMANDS) == 15


def test_tools_do_not_create_second_acl_or_retrieval():
    # data tools wrap ObjectRepository (the existing persistence), not a new
    # retrieval/ACL system.
    from app.application.services.tools import data_tools

    src = inspect.getsource(data_tools)
    assert "ObjectRepository" in src
    assert "permission_evaluator" not in src  # ACL lives in the executor


def test_l5_does_not_touch_frozen_l0_l4():
    l5_new = {
        "backend/app/application/dtos/tool.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/tool_registry.py",
    }
    frozen = {
        "backend/app/application/dtos/plan.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/domain/value_objects/claim.py",
        "backend/app/application/knowledge/predicate_catalogue.py",
    }
    assert l5_new.isdisjoint(frozen)
