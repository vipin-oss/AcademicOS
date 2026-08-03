"""Boundary query: Faculty report (PART 4)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetFacultyReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
