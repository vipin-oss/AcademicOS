"""Boundary query: PART 9 budget tracking — approved/released/utilized/remaining per project."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListBudgetLinesQuery:
    owner_user_id: str | None = None  # requesting principal (2026-09 audit follow-up)
