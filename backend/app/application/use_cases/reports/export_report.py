"""Use case: report export (PART 11).

Resolves the report kind, builds the SAME ``ReportView`` the workspace shows
(single composition point — the per-kind builders), and serialises it via the
stdlib exporters (PART 11). No new logic here — the export is the report,
byte-rendered.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.reports import ReportView
from app.application.queries.export_report import ExportReportQuery
from app.application.use_cases.reports.analytics_report import build_analytics_report
from app.application.use_cases.reports.committees_report import build_committees_report
from app.application.use_cases.reports.events_report import build_events_report
from app.application.use_cases.reports.exporters import EXPORTERS
from app.application.use_cases.reports.faculty_report import build_faculty_report
from app.application.use_cases.reports.finance_report import build_finance_report
from app.application.use_cases.reports.helpers import Snapshot
from app.application.use_cases.reports.publications_report import build_publications_report
from app.application.use_cases.reports.research_report import build_research_report
from app.application.use_cases.reports.students_report import build_students_report
from app.application.use_cases.reports.teaching_report import build_teaching_report
from app.application.use_cases.reports.academic_cv import build_academic_cv
from app.application.validators.reports import (
    assert_valid_export_format,
    assert_valid_report_kind,
)
from app.domain.repositories.object_repository import ObjectRepository


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    media_type: str
    filename: str


def build_report_view(kind: str, repository: ObjectRepository, filters) -> ReportView:
    """The one dispatch — export and routes share it (no duplicate routing)."""
    kind = assert_valid_report_kind(kind)
    snapshot = Snapshot(repository)
    builders = {
        "publications": lambda: build_publications_report(snapshot, filters),
        "research": lambda: build_research_report(repository, snapshot, filters),
        "faculty": lambda: build_faculty_report(repository, snapshot, filters),
        "students": lambda: build_students_report(repository, snapshot, filters),
        "teaching": lambda: build_teaching_report(repository, snapshot, filters),
        "finance": lambda: build_finance_report(repository, snapshot, filters),
        "events": lambda: build_events_report(snapshot, repository, filters),
        "committees": lambda: build_committees_report(repository, snapshot, filters),
        "analytics": lambda: build_analytics_report(snapshot, repository, filters),
        "academic_cv": lambda: build_academic_cv(repository, filters),
    }
    return builders[kind]()


def _filename(kind: str, extension: str) -> str:
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"academicos-{kind}-report-{stamp}.{extension}"


class ExportReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ExportReportQuery) -> ExportResult:
        kind = assert_valid_report_kind(query.kind)
        fmt = assert_valid_export_format(query.format)
        exporter, media_type, extension = EXPORTERS[fmt]
        view = build_report_view(kind, self._repository, query.filters)
        return ExportResult(
            content=exporter(view),
            media_type=media_type,
            filename=_filename(kind, extension),
        )
