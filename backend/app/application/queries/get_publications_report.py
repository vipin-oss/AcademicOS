"""Boundary query: Publications report (PART 2)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class GetPublicationsReportQuery:
    filters: ReportFilters = field(default_factory=ReportFilters)
