"""SQLAlchemy adapter for the ``EvalRunStore`` port (Sprint-7 M3).

The single writer of the ``eval_runs`` table, in the same shape as the
outbox relay: a thin ``Session`` wrapper that maps ``EvalRun`` records to
rows and back. One commit per appended run — a recorded run is durable
the moment ``add`` returns; a crash before the commit simply means the
run was never recorded (the runner re-runs it).

Row mapping is the only place that touches the table; the JSONB
per-case results are stored as plain dicts in suite order and
reconstructed into ``EvalResult`` objects on read.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.eval_run_store import EvalRunStore
from app.application.services.assistant_eval import EvalResult, EvalRun
from app.infrastructure.db.models.eval_run_model import EvalRunModel


def _results_to_json(results: tuple[EvalResult, ...]) -> list[dict]:
    return [
        {
            "name": result.name,
            "passed": result.passed,
            "details": list(result.details),
        }
        for result in results
    ]


def _results_from_json(payload: list) -> tuple[EvalResult, ...]:
    return tuple(
        EvalResult(
            name=str(entry["name"]),
            passed=bool(entry["passed"]),
            details=tuple(str(d) for d in entry["details"]),
        )
        for entry in payload
    )


class SQLEvalRunStore(EvalRunStore):
    """Persists ``EvalRun`` records to the ``eval_runs`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------- writes
    def add(self, run: EvalRun) -> None:
        self._session.add(
            EvalRunModel(
                run_id=run.run_id,
                model_id=run.model_id,
                model_version=run.model_version,
                prompt_id=run.prompt_id,
                prompt_version=run.prompt_version,
                passed=run.passed,
                total=run.total,
                results=_results_to_json(run.results),
                created_at=run.created_at,
            )
        )
        self._session.commit()

    # -------------------------------------------------------------- reads
    def get(self, run_id: str) -> EvalRun | None:
        rows = (
            self._session.execute(
                select(EvalRunModel).where(EvalRunModel.run_id == run_id)
            )
            .scalars()
            .all()
        )
        return self._from_row(rows[0]) if rows else None

    def latest_by_model(self, model_id: str) -> EvalRun | None:
        rows = (
            self._session.execute(
                select(EvalRunModel)
                .where(EvalRunModel.model_id == model_id)
                .order_by(EvalRunModel.created_at.desc(), EvalRunModel.id.desc())
                .limit(1)
            )
            .scalars()
            .all()
        )
        return self._from_row(rows[0]) if rows else None

    def recent_by_model(self, model_id: str, limit: int) -> list[EvalRun]:
        rows = (
            self._session.execute(
                select(EvalRunModel)
                .where(EvalRunModel.model_id == model_id)
                .order_by(EvalRunModel.created_at.desc(), EvalRunModel.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [self._from_row(row) for row in rows]

    # ------------------------------------------------------------- mapping
    @staticmethod
    def _from_row(row: EvalRunModel) -> EvalRun:
        return EvalRun(
            run_id=row.run_id,
            model_id=row.model_id,
            model_version=row.model_version,
            prompt_id=row.prompt_id,
            prompt_version=row.prompt_version,
            passed=row.passed,
            total=row.total,
            results=_results_from_json(row.results),
            created_at=row.created_at,
        )


__all__ = ["SQLEvalRunStore"]
