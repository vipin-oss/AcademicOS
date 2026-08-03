"""Boundary query: Events report (PART 8)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetEventsReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
