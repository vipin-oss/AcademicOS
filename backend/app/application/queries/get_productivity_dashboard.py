"""Boundary query: Productivity Hub dashboard (PART 6 cards)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetProductivityDashboardQuery:
    as_of: str | None = None  # testing seam; server defaults to today
