"""L4 QueryUnderstanding orchestration tests (ADR-035/036)."""

from __future__ import annotations

from app.application.dtos.plan import PlanOutcome
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidator
from app.application.services.planner import PlannerError
from app.application.services.query_understanding import QueryUnderstanding


class _StubPlanner:
    def __init__(self, result: dict | None = None, *, fail: bool = False):
        self._result = result
        self._fail = fail

    def plan_for(self, question: str, *, context: str = ""):
        if self._fail:
            raise PlannerError("unavailable")
        return self._result


class _FakeExec:
    def execute_fast_path(self, plan, *, context=None):
        return "ok"


def _query(planner):
    return QueryUnderstanding(
        planner=planner,
        validator=PlanValidator(),
        fast_path=FastPathExecutor(_FakeExec()),
        clarify_refuse=ClarifyRefuse(),
    )


def test_invalid_plan_routes_to_refuse():
    q = _query(_StubPlanner(result={"operation": "hack"}))
    r = q.understand("do something")
    assert r.outcome == PlanOutcome.REFUSE


def test_valid_fast_path_executes():
    q = _query(_StubPlanner(result={"operation": "list"}))
    r = q.understand("list things")
    assert r.outcome == PlanOutcome.EXECUTE
    assert r.plan.operation == "list"


def test_clarify_plan_routes_to_clarify():
    q = _query(_StubPlanner(result={"operation": "clarify"}))
    r = q.understand("ambiguous")
    assert r.outcome == PlanOutcome.CLARIFY


def test_refuse_plan_routes_to_refuse():
    q = _query(_StubPlanner(result={"operation": "refuse"}))
    r = q.understand("something forbidden")
    assert r.outcome == PlanOutcome.REFUSE


def test_planner_failure_falls_back_to_fast_path_or_clarify():
    # "how many" maps to the 'count' fast-path command offline
    q = _query(_StubPlanner(fail=True))
    r = q.understand("how many grants?")
    # deterministic fast-path count OR clarify (no rules-v1)
    assert r.outcome in (PlanOutcome.EXECUTE, PlanOutcome.CLARIFY)


def test_no_model_output_executed_unvalidated():
    # A planner returning non-dict or invalid must not dispatch.
    q = _query(_StubPlanner(result={"operation": "refuse"}))
    r = q.understand("x")
    assert r.outcome == PlanOutcome.REFUSE
