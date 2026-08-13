"""L4 clarify / refuse protocol (Freeze Contract §16, §17, ADR-020).

Explicit machine-readable outcomes, not generic assistant text. Uses the frozen
capability semantics (``clarify`` / ``refuse`` in the capability registry).
Refusal is deterministic when evidence, ACL, or policy forbids an answer; never
LLM-arbitrated.
"""

from __future__ import annotations

from app.application.dtos.plan import Plan, PlanOutcome, PlanResult


class ClarifyRefuse:
    def clarify(self, *, question: str = "") -> PlanResult:
        """Produce a machine-readable clarify outcome."""
        return PlanResult(
            outcome=PlanOutcome.CLARIFY,
            plan=Plan(operation="clarify", output_kind="clarification"),
            clarify_question=question or "Please clarify what you are asking.",
        )

    def refuse(self, *, reason: str = "") -> PlanResult:
        """Produce a deterministic refuse outcome."""
        return PlanResult(
            outcome=PlanOutcome.REFUSE,
            plan=Plan(operation="refuse", output_kind="answer"),
            reason=reason or "Cannot answer within evidence, ACL, or policy.",
        )

    def decide(
        self,
        *,
        plan: Plan | None,
        needs_clarify: bool = False,
        refusal_reason: str | None = None,
    ) -> PlanResult:
        """Route a validated (or missing) plan to execute / clarify / refuse."""
        if refusal_reason is not None:
            return self.refuse(reason=refusal_reason)
        if needs_clarify:
            return self.clarify()
        if plan is None:
            return self.refuse(reason="No valid plan could be produced.")
        return PlanResult(outcome=PlanOutcome.EXECUTE, plan=plan)


__all__ = ["ClarifyRefuse"]
