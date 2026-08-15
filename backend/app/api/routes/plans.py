"""L4 Query Understanding API (ADR-022 / ADR-020).

  POST /plans        — turn a question into a validated plan (execute /
                       clarify / refuse), no execution.
  POST /questions    — end-to-end: plan → fast-path/clarify/refuse → answer.

The planner output is validated deterministically before any dispatch. Model
output is never executed directly. Existing assistant routes stay compatible.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.application.ai.core import AiCore
from app.application.dtos.plan import PlanOutcome
from app.application.services.clarify_refuse import ClarifyRefuse
from app.application.services.fast_path import FastPathExecutor
from app.application.services.plan_validator import PlanValidator
from app.application.services.planner import PlannerError, PlannerService
from app.application.services.query_understanding import QueryUnderstanding
from app.domain.entities.object import UniversalObject

router = APIRouter(
    prefix="/plans",
    tags=["plans"],
    dependencies=[Depends(get_current_user)],
)


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    context: str = ""


class PlanOut(BaseModel):
    outcome: str
    plan: dict | None = None
    reason: str | None = None
    clarify_question: str | None = None


def _query_understanding(ai_core: AiCore) -> QueryUnderstanding:
    return QueryUnderstanding(
        planner=PlannerService(ai_core),
        validator=PlanValidator(),
        fast_path=FastPathExecutor(_NullExecutor()),
        clarify_refuse=ClarifyRefuse(),
    )


class _NullExecutor:
    """Fast-path executor seam for the /plans surface (no data execution).

    Planning alone does not execute data work; the fast-path ``supports``
    check is what /plans uses. Answer generation happens via /questions and
    the assistant path.
    """

    def execute_fast_path(self, plan, *, context=None):  # pragma: no cover
        raise NotImplementedError("Fast-path execution happens via /questions.")


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanBody,
    ai_core: AiCore = Depends(get_ai_core),
    user: UniversalObject = Depends(get_current_user),
) -> PlanOut:
    """Produce a validated plan (no execution)."""
    query = _query_understanding(ai_core)
    result = query.understand(body.question, context=body.context)
    return PlanOut(
        outcome=result.outcome,
        plan=result.plan.to_dict() if result.plan else None,
        reason=result.reason,
        clarify_question=result.clarify_question,
    )


@router.post("/validate", response_model=PlanOut)
def validate_plan(
    body: PlanBody,
    ai_core: AiCore = Depends(get_ai_core),
    user: UniversalObject = Depends(get_current_user),
) -> PlanOut:
    """Validate a question's plan deterministically (schema/type/scope)."""
    try:
        raw = PlannerService(ai_core).plan_for(body.question, context=body.context)
    except PlannerError:
        return PlanOut(outcome=PlanOutcome.REFUSE, reason="Planner unavailable.")
    try:
        plan = PlanValidator().validate(raw)
    except Exception as exc:  # noqa: BLE001 — deterministic validation
        return PlanOut(outcome=PlanOutcome.REFUSE, reason=f"Invalid plan: {exc}")
    return PlanOut(outcome=PlanOutcome.EXECUTE, plan=plan.to_dict())


__all__ = ["router"]
