"""Boundary query: Research report (PART 3)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetResearchReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
