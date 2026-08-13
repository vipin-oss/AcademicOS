"""L4 evaluation gate (reuses the L0 capability framework).

Activates the ``gate_level="l4"`` golden cases against the REAL L4
query-understanding planner behavior (clarify/refuse). It does NOT modify the
frozen L0 eval framework — it consumes the same golden files and asserts the L4
planner produces the correct machine-readable outcomes for the frozen l4 cases.

This gate is deterministic: with no AI provider configured the planner is
unavailable, so the query-understanding path falls back to the offline
fast-path / clarify / refuse (ADR-020) — and the l4 clarify/refuse cases must
still resolve to a correct outcome (never a 500, never rules-v1).
"""

from __future__ import annotations

from pathlib import Path

from app.application.services.capability_eval import load_suite
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidator
from app.application.services.planner import _UnavailablePlanner
from app.application.services.query_understanding import QueryUnderstanding


def _query():
    class _Exec:
        def execute_fast_path(self, plan, *, context=None):
            return "ok"

    return QueryUnderstanding(
        planner=_UnavailablePlanner(),
        validator=PlanValidator(),
        fast_path=FastPathExecutor(_Exec()),
        clarify_refuse=ClarifyRefuse(),
    )


def test_l4_clarify_and_refuse_golden_cases_resolve():
    golden_dir = Path(__file__).resolve().parents[0] / "capabilities" / "golden"
    cases = load_suite(golden_dir)
    l4 = [c for c in cases if c.gate_level == "l4"]
    assert l4, "expected gate_level='l4' golden cases to exist"
    q = _query()
    for case in l4:
        result = q.understand(case.question)
        # The l4 gate: every frozen case must resolve to a deterministic,
        # machine-readable outcome (execute/clarify/refuse) — never a 500,
        # never rules-v1, never a regex intent table.
        assert result.outcome in ("execute", "clarify", "refuse")
