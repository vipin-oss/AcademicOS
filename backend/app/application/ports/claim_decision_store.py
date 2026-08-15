"""Application port: claim-decision audit store (L3, ADR-032).

Append-only, idempotent-by-``decision_id``. Claim-scoped — deliberately NOT the
conversation-scoped ``ReviewDecisionStore``, so document decisions never couple
to assistant reviews. ``decision_id`` uniqueness makes a duplicate decision a
no-op (never a second row).
"""

from __future__ import annotations

import abc

from app.application.services.decision_records import DecisionRecord


class ClaimDecisionStore(abc.ABC):
    @abc.abstractmethod
    def add(self, record: DecisionRecord) -> DecisionRecord:
        """Append one immutable decision row; returns it as stored.

        Idempotent by ``decision_id``: re-adding the same id is a no-op.
        """

    @abc.abstractmethod
    def by_claim(self, claim_id: str) -> list[DecisionRecord]:
        """Full audit trail of one claim, chronological (oldest first)."""

    @abc.abstractmethod
    def recent(self, limit: int = 50) -> list[DecisionRecord]:
        """Most recent claim decisions, newest first (bounded)."""

    @abc.abstractmethod
    def recent_corrections(self, limit: int = 200) -> list[DecisionRecord]:
        """Most recent ``correct`` decisions, newest first (bounded).

        V3 M7 extraction-health signal: the human fixes that point at the
        predicates the extractor keeps getting wrong.
        """
