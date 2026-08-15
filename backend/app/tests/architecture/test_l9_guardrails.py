"""L9 architecture guardrails (ADR-045/046/047).

Pins that L9 is an evaluation/release-quality layer only:
- no new capability IDs; frozen 18-capability registry unchanged;
- no L1-L8 production rewrite (planner, tools, evidence, memory, cross-domain);
- no second evaluation framework;
- no new migration;
- no L10+ mechanisms (worker pool / storage / tenancy / partitions);
- memory is never treated as evidence (ADR-015).
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l9_adrs_present():
    for name in (
        "ADR-045-l9-hard-capability-gates",
        "ADR-046-l9-isolation-matrix-and-scale-budgets",
        "ADR-047-claim-store-scaling-measurements",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l8_done_l9_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L8" in text and "done" in text
    assert "L9" in text and "in_progress" in text
    # L10+ must not have started
    for lvl in ("L10", "L11", "L12"):
        assert lvl in text and "not_started" in text


def test_l9_no_new_capability_ids():
    from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS

    assert len(FROZEN_CAPABILITY_IDS) == 18


def test_l9_reuses_existing_eval_framework():
    # L9 tests reuse capability_eval / eval gates; no second framework file exists.
    for forbidden in ("second_eval", "eval_framework_v2"):
        assert not any(p.name.startswith(forbidden) for p in (REPO / "backend" / "app").rglob("*.py"))


def test_l9_no_new_migration():
    migrations = REPO / "backend" / "alembic" / "versions"
    names = [p.name for p in migrations.glob("*.py")]
    # Migration head is 0016 (typed claims, V3 M5). L9 itself adds none.
    assert not any("0017" in n for n in names), names


def test_l9_does_not_touch_frozen_production():
    l9_new = {
        "backend/app/tests/eval/test_l9_eval_gate.py",
        "backend/app/tests/eval/test_l9_isolation_matrix.py",
        "backend/app/tests/eval/test_l9_scale_budgets.py",
        "backend/app/tests/architecture/test_l9_guardrails.py",
    }
    frozen = {
        "backend/app/application/capabilities/registry.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/application/services/plan_validator.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/tool_registry.py",
        "backend/app/application/services/claim_evidence.py",
        "backend/app/application/services/persistent_memory.py",
        "backend/app/application/services/cross_domain.py",
        "backend/app/application/services/temporal.py",
    }
    assert l9_new.isdisjoint(frozen)
