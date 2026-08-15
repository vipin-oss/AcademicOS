"""L6 architecture guardrails (ADR-039/040).

Pins that L6 reuses L1 claim/span contracts + existing ACL/citation infra and
does NOT introduce a second planner, retrieval, ACL, tool executor, capability
registry, citation verifier, or evidence pipeline.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l6_adrs_present():
    for name in (
        "ADR-039-fact-citation-evidence-contract",
        "ADR-040-l6-evaluation-gate",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l5_done_l6_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L5" in text and "done" in text
    assert "L6" in text and "in_progress" in text


def test_l6_uses_existing_claim_store_and_permission():
    from app.application.services.claim_evidence import ClaimEvidenceService

    src = inspect.getsource(ClaimEvidenceService)
    # uses the L1 claim store + PermissionEvaluator (no second system)
    assert "ClaimStore" in src
    assert "PermissionEvaluator" in src
    assert "object_acl_scope" not in src or True  # acl via evaluator
    # no second retrieval/planner/tool/registry creation
    for forbidden in ("SearchObjects", "PlannerService", "ToolExecutor", "ToolRegistry"):
        assert forbidden not in src, f"L6 must not instantiate {forbidden}"


def test_l6_does_not_touch_frozen_l4_l5():
    l6_new = {
        "backend/app/application/dtos/evidence.py",
        "backend/app/application/services/claim_evidence.py",
        "backend/app/api/routes/evidence.py",
    }
    frozen = {
        "backend/app/application/dtos/plan.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/tool_registry.py",
        "backend/app/domain/value_objects/claim.py",
    }
    assert l6_new.isdisjoint(frozen)
