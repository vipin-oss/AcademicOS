"""Query (CQRS intent) for the faculty Teaching dashboard (PART J)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetTeachingDashboardQuery:
    """Intent to aggregate Classes / Students / Assignments / Submission
    signals across every Class the installation teaches."""

    attendance_threshold: float = 75.0
