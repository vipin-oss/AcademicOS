"""Boundary query: the PART 8 committees & meetings dashboard."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetCommitteesDashboardQuery:
    upcoming_limit: int = 10
