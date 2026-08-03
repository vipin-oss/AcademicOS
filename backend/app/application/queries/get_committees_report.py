"""Boundary query: Committee report (PART 9)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetCommitteesReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
