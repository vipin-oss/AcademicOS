"""Application port: AI spend ledger (V3 M12, ADR-059).

Append-only, immutable spend audit. The budget policy aggregates it; rows are
never updated or deleted.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class SpendRecord:
    id: str
    tenant_id: str
    user_id: str
    provider_id: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    created_at: str = ""


class SpendLedger(abc.ABC):
    @abc.abstractmethod
    def record(self, spend: SpendRecord) -> SpendRecord:
        """Append one immutable spend row (idempotent by id)."""

    @abc.abstractmethod
    def total_for_user(self, user_id: str) -> float:
        """Sum of estimated_cost_usd for one user."""

    @abc.abstractmethod
    def total_for_tenant(self, tenant_id: str) -> float:
        """Sum of estimated_cost_usd for one tenant."""
