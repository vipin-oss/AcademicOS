"""Query (CQRS intent) for the Research dashboard (PART 10)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetResearchDashboardQuery:
    """Intent to compute the dashboard cards + upcoming deadlines."""

    upcoming_limit: int = 10
    overdue_days: int = 0  # 0 = include every pending milestone (overdue first)
