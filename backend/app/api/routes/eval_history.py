"""REST routes for evaluation history & benchmark comparison (Sprint-7 M4).

Read-only HTTP surface over the EXISTING ``EvaluationHistory`` service
(Sprint-7 M3 persistence). Mirrors ``routes/assistant.py`` conventions
exactly: router-level authentication, ``_not_found``/``_unprocessable``
mapping, strict request bodies (extra=forbid), ``asdict``-shaped
responses via the shared assistant mapper.

Every endpoint calls the ``EvaluationHistory`` service only — no
comparison, query, or persistence logic lives in the route. The model
registry is intentionally NOT consulted: history serves the stored
records even for models that were unregistered since their runs were
recorded (config may change; benchmark records must not).

Surface:
    GET  /assistant/eval/runs                        list runs, newest first
                                                     (optional model filter)
    GET  /assistant/eval/runs/{run_id}               one run
    POST /assistant/eval/compare                     compare any two runs
    GET  /assistant/eval/models/{model_id}/compare/latest
                                                     regression detection over
                                                     the two most recent runs
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.assistant_mapper import eval_run_dict, run_comparison_dict
from app.application.services.assistant_eval import EvaluationHistory
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.eval_run_store import SQLEvalRunStore

router = APIRouter(
    prefix="/assistant/eval",
    tags=["Assistant"],
    dependencies=[Depends(get_current_user)],
)


def get_eval_history(db: Session = Depends(get_db)) -> EvaluationHistory:
    """Composition seam (Sprint-7 M4): the evaluation-history service over
    the durable ``eval_runs`` store. Integration tests override this
    dependency to seed and control the history."""
    return EvaluationHistory(SQLEvalRunStore(db))


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


class CompareBody(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    base_run_id: str
    candidate_run_id: str


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
@router.get("/runs")
def list_eval_runs(
    model_id: str | None = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    history: EvaluationHistory = Depends(get_eval_history),
):
    """Historical evaluation runs, newest first. ``model_id`` filters to one
    model; without it the whole history is returned (dashboard view)."""
    runs = history.recent(model_id, limit) if model_id else history.recent_all(limit)
    return {"items": [eval_run_dict(run) for run in runs]}


@router.get("/runs/{run_id}")
def get_eval_run(
    run_id: str,
    history: EvaluationHistory = Depends(get_eval_history),
):
    """One recorded evaluation run with its per-case benchmark results."""
    run = history.get(run_id)
    if run is None:
        raise _not_found(f"Unknown evaluation run: {run_id}")
    return eval_run_dict(run)


# ---------------------------------------------------------------------------
# Comparison / regression detection
# ---------------------------------------------------------------------------
@router.post("/compare")
def compare_eval_runs(
    body: CompareBody,
    history: EvaluationHistory = Depends(get_eval_history),
):
    """Deterministic diff of two recorded runs: regression/fix/stable
    summaries. 404 when a run is unknown; 422 when the runs cover
    different case sets (a comparison would be meaningless)."""
    base = history.get(body.base_run_id)
    if base is None:
        raise _not_found(f"Unknown evaluation run: {body.base_run_id}")
    candidate = history.get(body.candidate_run_id)
    if candidate is None:
        raise _not_found(f"Unknown evaluation run: {body.candidate_run_id}")
    try:
        comparison = history.compare(base, candidate)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    return run_comparison_dict(comparison)


@router.get("/models/{model_id}/compare/latest")
def compare_latest_eval_runs(
    model_id: str,
    history: EvaluationHistory = Depends(get_eval_history),
):
    """Historical regression detection: the two most recent recorded runs of
    ``model_id`` (candidate = newest). 404 when fewer than two runs exist."""
    comparison = history.compare_latest(model_id)
    if comparison is None:
        raise _not_found(
            f"Model {model_id!r} has fewer than two recorded runs; "
            "no comparison is available."
        )
    return run_comparison_dict(comparison)
