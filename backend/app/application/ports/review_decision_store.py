"""Port: review-decision persistence (Sprint-7 M5).

The single seam between the human review loop (application) and durable
storage (infrastructure) — the same doctrine as ``eval_run_store``: the
port carries the application ``ReviewDecision`` record; runs are
append-only; ``decision_id`` is the idempotency key (recording the same
decision twice is a unique-violation, never a duplicate row).

Contract:

- ``add`` appends one immutable decision row.
- ``by_conversation`` — the full audit trail of one conversation,
  chronological (oldest first).
- ``recent`` — the workspace activity feed, newest first (bounded).
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — no runtime dependency (no cycle)
    from app.application.services.assistant_review import ReviewDecision


class ReviewDecisionStore(abc.ABC):
    @abc.abstractmethod
    def add(self, decision: ReviewDecision) -> ReviewDecision:
        """Append one immutable review-decision row; returns it as stored."""

    @abc.abstractmethod
    def by_conversation(self, conversation_id: str) -> list[ReviewDecision]:
        """The complete audit trail of ``conversation_id``, oldest first."""

    @abc.abstractmethod
    def recent(self, limit: int) -> list[ReviewDecision]:
        """The ``limit`` most recent decisions across all conversations,
        newest first (deterministic tie-breaks)."""
