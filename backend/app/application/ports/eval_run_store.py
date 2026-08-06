"""Port: evaluation-run persistence (Sprint-7 M3).

The single seam between benchmark history (application) and durable
storage (infrastructure). The port carries the application ``EvalRun``
record — evaluation runs are application artifacts, so the port lives in
the application layer (same doctrine as ``assistant_provider``, which
carries application DTOs).

Contract:

- ``add`` appends one immutable run record. Runs are never updated, so a
  recorded run can never change afterwards (benchmark history cannot
  drift stale). ``run_id`` is the idempotency key: recording the same
  run twice is a unique-violation, never a duplicate row.
- ``get`` / ``latest_by_model`` / ``recent_by_model`` serve the history
  and regression-detection reads; per-model queries return runs newest
  first (deterministic tie-breaks).
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — no runtime dependency (no cycle)
    from app.application.services.assistant_eval import EvalRun


class EvalRunStore(abc.ABC):
    @abc.abstractmethod
    def add(self, run: EvalRun) -> None:
        """Append one immutable run record."""

    @abc.abstractmethod
    def get(self, run_id: str) -> EvalRun | None:
        """The run with ``run_id``, or ``None`` when unknown."""

    @abc.abstractmethod
    def latest_by_model(self, model_id: str) -> EvalRun | None:
        """The most recent recorded run of ``model_id``, or ``None``."""

    @abc.abstractmethod
    def recent_by_model(self, model_id: str, limit: int) -> list[EvalRun]:
        """The ``limit`` most recent runs of ``model_id``, newest first."""
