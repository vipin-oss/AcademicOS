"""Application port: CDM-decision audit store (L3, ADR-032).

Append-only, idempotent-by-``decision_id`` audit of human decisions on CDM
blocks. Mirror of ``ClaimDecisionStore`` for the block plane.
"""

from __future__ import annotations

import abc

from app.application.services.decision_records import DecisionRecord


class CdmDecisionStore(abc.ABC):
    @abc.abstractmethod
    def add(self, record: DecisionRecord) -> DecisionRecord:
        """Append one immutable decision row (idempotent by decision_id)."""

    @abc.abstractmethod
    def by_block(self, block_id: str) -> list[DecisionRecord]:
        """Audit trail of one block, chronological."""

    @abc.abstractmethod
    def recent(self, limit: int = 50) -> list[DecisionRecord]:
        """Most recent block decisions, newest first."""
