"""Boundary query: Student report (PART 5)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetStudentsReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
