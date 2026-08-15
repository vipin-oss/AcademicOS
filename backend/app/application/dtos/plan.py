"""L4 plan schema — frozen plan DTO (Freeze Contract §16).

A validated execution plan produced by the model-driven planner. The schema is
frozen: ``{operation, domains[], entities[], time_range, filters{},
output_kind, evidence_required, sub_plans[]}``. ``operation`` MUST be one of
the frozen capability registry ids. Model output is untrusted; only validated
plans are dispatched.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    operation: str
    domains: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    time_range: str | None = None
    filters: dict[str, object] = field(default_factory=dict)
    output_kind: str = "answer"
    evidence_required: bool = False
    sub_plans: tuple[Plan, ...] = ()

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "domains": list(self.domains),
            "entities": list(self.entities),
            "time_range": self.time_range,
            "filters": self.filters,
            "output_kind": self.output_kind,
            "evidence_required": self.evidence_required,
            "sub_plans": [p.to_dict() for p in self.sub_plans],
        }


#: Plan decisions (clarify/refuse) are explicit machine-readable outcomes.
class PlanOutcome(str):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    REFUSE = "refuse"


@dataclass(frozen=True)
class PlanResult:
    outcome: str
    plan: Plan | None = None
    reason: str | None = None
    clarify_question: str | None = None


__all__ = ["Plan", "PlanOutcome", "PlanResult"]
