"""Wire <-> boundary mapping for the Reports & Analytics API.

Mirrors ``events_mapper`` / ``finance_mapper``: query-string parameters become
boundary query inputs, output DTOs become plain response dictionaries. The
reports module is read-only, so only the output direction (plus the filter
params translation) lives here.
"""
from __future__ import annotations

from app.application.dtos.reports import (
    FILTER_KEYS_BY_KIND,
    REPORT_TITLES,
    ReportChart,
    ReportFilters,
    ReportKpi,
    ReportsDashboard,
    ReportTable,
    ReportView,
)
from app.application.queries.export_report import ExportReportQuery


def to_report_filters(*, params: dict) -> ReportFilters:
    """Translate raw query params to the boundary ``ReportFilters``.

    ``year`` arrives as a string; non-integer values surface as ValidationError
    on the boundary validator (422), so only the int-or-None normalisation
    happens here — consistent with the events list year param.
    """
    year_raw = params.get("year")
    year: int | None = None
    if year_raw is not None and str(year_raw).strip():
        try:
            year = int(str(year_raw).strip())
        except ValueError:
            year = -1  # invalid marker -> 422 from the boundary validator
    return ReportFilters(
        year=year,
        date_from=params.get("date_from"),
        date_to=params.get("date_to"),
        faculty_id=params.get("faculty_id"),
        student_id=params.get("student_id"),
        project_id=params.get("project_id"),
        grant_id=params.get("grant_id"),
        department=params.get("department"),
        event_id=params.get("event_id"),
        committee_id=params.get("committee_id"),
    )


def to_export_query(*, kind: str, format: str, params: dict) -> ExportReportQuery:
    return ExportReportQuery(kind=kind, format=format, filters=to_report_filters(params=params))


def dashboard_response(out: ReportsDashboard) -> dict:
    return {
        "total_publications": out.total_publications,
        "total_projects": out.total_projects,
        "total_grants": out.total_grants,
        "total_students": out.total_students,
        "total_classes": out.total_classes,
        "total_faculty": out.total_faculty,
        "total_committees": out.total_committees,
        "total_events": out.total_events,
        "budget_approved": out.budget_approved,
        "budget_utilized": out.budget_utilized,
        "budget_remaining": out.budget_remaining,
    }


def _kpi_response(kpi: ReportKpi) -> dict:
    return {"label": kpi.label, "value": kpi.value}


def _table_response(table: ReportTable) -> dict:
    return {
        "key": table.key,
        "title": table.title,
        "columns": list(table.columns),
        "rows": [list(row) for row in table.rows],
        "hrefs": ([list(row) for row in table.hrefs] if table.hrefs is not None else None),
    }


def _chart_response(chart: ReportChart) -> dict:
    return {
        "key": chart.key,
        "title": chart.title,
        "kind": chart.kind,
        "labels": list(chart.labels),
        "series": [{"name": series.name, "data": list(series.data)} for series in chart.series],
    }


def report_response(out: ReportView) -> dict:
    return {
        "kind": out.kind,
        "title": out.title,
        "generated_at": out.generated_at,
        "applied_filters": dict(out.applied_filters),
        "kpis": [_kpi_response(kpi) for kpi in out.kpis],
        "tables": [_table_response(table) for table in out.tables],
        "charts": [_chart_response(chart) for chart in out.charts],
    }


def catalogue_response() -> dict:
    """The module's report catalogue (kinds the workspace can open + which
    PART 12 filters each honours) — the frontend renders pickers from this
    single source of truth."""
    return {
        "kinds": [
            {
                "key": kind,
                "title": REPORT_TITLES[kind],
                "filters": list(FILTER_KEYS_BY_KIND[kind]),
            }
            for kind in REPORT_TITLES
        ]
    }
