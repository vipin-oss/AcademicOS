"""L4 clarify/refuse protocol tests (ADR-035, §16/§17)."""

from __future__ import annotations

from app.application.dtos.plan import Plan, PlanOutcome
from app.application.services.clarify_refuse import ClarifyRefuse


def test_clarify_is_machine_readable():
    r = ClarifyRefuse().clarify(question="Which letter?")
    assert r.outcome == PlanOutcome.CLARIFY
    assert r.plan.operation == "clarify"
    assert r.clarify_question == "Which letter?"


def test_refuse_is_deterministic():
    r = ClarifyRefuse().refuse(reason="No evidence.")
    assert r.outcome == PlanOutcome.REFUSE
    assert r.plan.operation == "refuse"
    assert r.reason == "No evidence."


def test_decide_routes_execute():
    r = ClarifyRefuse().decide(plan=Plan(operation="list"))
    assert r.outcome == PlanOutcome.EXECUTE
    assert r.plan.operation == "list"


def test_decide_refuses_when_no_plan():
    r = ClarifyRefuse().decide(plan=None)
    assert r.outcome == PlanOutcome.REFUSE


def test_decide_clarify_when_ambiguous():
    r = ClarifyRefuse().decide(plan=None, needs_clarify=True)
    assert r.outcome == PlanOutcome.CLARIFY


def test_decide_refuses_on_policy_reason():
    r = ClarifyRefuse().decide(plan=Plan(operation="list"), refusal_reason="denied")
    assert r.outcome == PlanOutcome.REFUSE
