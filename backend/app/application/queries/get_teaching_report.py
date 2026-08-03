"""Boundary query: Teaching report (PART 6)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetTeachingReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
