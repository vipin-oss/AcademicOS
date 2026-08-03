"""Boundary query: Analytics (PART 10)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetAnalyticsReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
