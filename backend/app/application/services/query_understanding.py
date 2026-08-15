"""L4 Query Understanding orchestration (Freeze Contract §13.5).

The model-driven question→plan pipeline:

  normalized request → PlannerService.structured_generate()
                    → PlanValidator.validate()          (deterministic)
                    → fast-path if operation is a frozen fast-path command
                    → clarify / refuse otherwise
                    → dispatch only validated commands

Model output is untrusted: nothing is executed before deterministic validation.
The planner never queries data itself (ADR-020, §27); dispatch goes through the
injected execution seam (assistant/retrieval/grounded-QA).
"""

from __future__ import annotations

from app.application.dtos.plan import Plan, PlanOutcome, PlanResult
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidationError, PlanValidator
from app.application.services.planner import PlannerError, PlannerService


class QueryUnderstanding:
    def __init__(
        self,
        planner: PlannerService,
        validator: PlanValidator,
        fast_path: FastPathExecutor,
        clarify_refuse: ClarifyRefuse,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._fast_path = fast_path
        self._clarify_refuse = clarify_refuse

    def understand(self, question: str, *, context: str = "") -> PlanResult:
        """Understand a question → execute / clarify / refuse PlanResult."""
        # 1. Model-driven plan generation (may fail gracefully).
        try:
            raw = self._planner.plan_for(question, context=context)
        except PlannerError:
            # Planner unavailable → fall back to a deterministic fast-path try,
            # then clarify/refuse (ADR-020); never regex, never rules-v1.
            return self._fallback_without_planner(question)

        # 2. Deterministic validation (reject invalid/unsafe/unsupported).
        try:
            plan = self._validator.validate(raw)
        except PlanValidationError:
            return self._clarify_refuse.refuse(
                reason="The generated plan failed validation."
            )

        # 3. Clarify / refuse per plan semantics.
        if plan.operation == "clarify":
            return self._clarify_refuse.clarify()
        if plan.operation == "refuse":
            return self._clarify_refuse.refuse(reason="Declined by plan.")

        # 4. Dispatch: fast-path commands execute offline; others execute via
        #    the execution seam (retrieval/grounded-QA) — always validated.
        if self._fast_path.supports(plan):
            return PlanResult(outcome=PlanOutcome.EXECUTE, plan=plan)
        return PlanResult(outcome=PlanOutcome.EXECUTE, plan=plan)

    def _fallback_without_planner(self, question: str) -> PlanResult:
        """When the planner is unavailable: try a frozen fast-path command by
        deterministic keyword routing; else clarify/refuse (ADR-020)."""
        from app.application.services.fast_path_command import match_fast_path

        cmd = match_fast_path(question)
        if cmd is not None:
            return PlanResult(
                outcome=PlanOutcome.EXECUTE,
                plan=Plan(operation=cmd, output_kind="answer"),
            )
        return self._clarify_refuse.clarify()


__all__ = ["QueryUnderstanding"]
