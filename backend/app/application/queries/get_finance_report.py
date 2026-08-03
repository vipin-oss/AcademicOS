"""Boundary query: Finance report (PART 7)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetFinanceReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
