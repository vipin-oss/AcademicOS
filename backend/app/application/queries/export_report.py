"""Boundary query: report export (PART 11 — pdf | csv | xlsx)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.reports import ReportFilters


@dataclass
class ExportReportQuery:
    kind: str                        # REPORT_KINDS
    format: str                      # EXPORT_FORMATS
    filters: ReportFilters = field(default_factory=ReportFilters)
