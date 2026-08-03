"""Use case: Analytics (PART 10).

Year-wise trend charts across the frozen modules — publication trend, event
trend, budget trend (approved vs utilized per project start year), teaching
load (weekly hours per faculty — the Faculty module's ``classes_of_faculty``
composition), student attendance trend (effective presence % per month, the
teaching module's documented convention). Chart-first view (plus one year
rollup table): every point is computed from the source modules at request
time. The analytics lens intentionally honours NO PART 12 pickers
(``FILTER_KEYS_BY_KIND["analytics"] == ()``) — it IS the cross-module zoom-out.
"""
from __future__ import annotations

from app.application.dtos.events import KEY_START_DATE as KEY_EVENT_START
from app.application.dtos.publication import KEY_DATE, KEY_YEAR
from app.application.dtos.reports import (
    CHART_BAR,
    CHART_LINE,
    ReportChart,
    ReportChartSeries,
    ReportView,
)
from app.application.dtos.research import KEY_BUDGET_APPROVED, KEY_BUDGET_UTILIZED
from app.application.dtos.research import KEY_START_DATE as KEY_PROJECT_START
from app.application.dtos.teaching import (
    KEY_ATTENDANCE_RECORDS,
    KEY_SESSION_DATE,
    parse_json_object,
)
from app.application.queries.get_analytics_report import GetAnalyticsReportQuery
from app.application.use_cases.faculty.helpers import classes_of_faculty
from app.application.use_cases.reports.helpers import (
    Snapshot,
    fmt_int,
    fmt_money,
    fmt_pct,
    iso_date,
    kpi,
    line_chart,
    meta_of,
    now_iso,
    parse_amount,
    table,
    year_of,
)
from app.application.use_cases.reports.students_report import EFFECTIVE_STATES
from app.application.use_cases.teaching.helpers import enrolled_students
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import RelationshipKind

KIND = "analytics"
REPORT_TITLE = "Analytics"


def _year_span(snapshot: Snapshot) -> list[int]:
    years: set[int] = set()
    for pub in snapshot["publications"]:
        year = year_of(meta_of(pub).get(KEY_DATE) or meta_of(pub).get(KEY_YEAR))
        if year is not None:
            years.add(year)
    for event in snapshot["events"]:
        year = year_of(meta_of(event).get(KEY_EVENT_START))
        if year is not None:
            years.add(year)
    for project in snapshot["projects"]:
        year = year_of(meta_of(project).get(KEY_PROJECT_START))
        if year is not None:
            years.add(year)
    return sorted(years)


def build_analytics_report(snapshot: Snapshot, repository: ObjectRepository, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    years = _year_span(snapshot)
    labels = [str(y) for y in years]

    pub_by_year = {y: 0 for y in years}
    for pub in snapshot["publications"]:
        year = year_of(meta_of(pub).get(KEY_DATE) or meta_of(pub).get(KEY_YEAR))
        if year in pub_by_year:
            pub_by_year[year] += 1
    event_by_year = {y: 0 for y in years}
    for event in snapshot["events"]:
        year = year_of(meta_of(event).get(KEY_EVENT_START))
        if year in event_by_year:
            event_by_year[year] += 1
    approved_by_year = {y: 0.0 for y in years}
    utilized_by_year = {y: 0.0 for y in years}
    for project in snapshot["projects"]:
        year = year_of(meta_of(project).get(KEY_PROJECT_START))
        if year not in approved_by_year:
            continue
        meta = meta_of(project)
        approved_by_year[year] += parse_amount(meta.get(KEY_BUDGET_APPROVED)) or 0.0
        utilized_by_year[year] += parse_amount(meta.get(KEY_BUDGET_UTILIZED)) or 0.0

    # Teaching load — weekly hours per faculty (frozen Faculty composition).
    load_labels: list[str] = []
    load_hours: list[float] = []
    for member in sorted(snapshot["faculty"], key=lambda o: (o.title.casefold(), str(o.id))):
        _, hours = classes_of_faculty(repository, str(member.id))
        load_labels.append(member.title)
        load_hours.append(round(hours, 2))

    # Student attendance trend — effective presence % per month (teaching
    # convention: no record = absent; late/medical count toward presence).
    month_effective: dict[str, int] = {}
    month_recorded: dict[str, int] = {}
    roster_cache: dict[str, list] = {}
    for session in snapshot["attendance_sessions"]:
        parsed = iso_date(meta_of(session).get(KEY_SESSION_DATE))
        if parsed is None:
            continue
        month = parsed.strftime("%Y-%m")
        class_ids = [
            str(rel.target)
            for rel in session.relationships
            if rel.kind is RelationshipKind.BELONGS_TO
        ]
        if not class_ids:
            continue
        class_id = class_ids[0]
        if class_id not in roster_cache:
            roster_cache[class_id] = enrolled_students(repository, class_id)
        records = parse_json_object(meta_of(session).get(KEY_ATTENDANCE_RECORDS))
        for student in roster_cache[class_id]:
            month_recorded[month] = month_recorded.get(month, 0) + 1
            if records.get(str(student.id), "absent") in EFFECTIVE_STATES:
                month_effective[month] = month_effective.get(month, 0) + 1
    month_labels = sorted(month_recorded)
    month_pcts = [
        round(month_effective.get(m, 0) / month_recorded[m] * 100, 2) if month_recorded[m] else 0.0
        for m in month_labels
    ]

    rollup_rows = [
        [
            str(year),
            fmt_int(pub_by_year.get(year, 0)),
            fmt_int(event_by_year.get(year, 0)),
            fmt_money(approved_by_year.get(year, 0.0)),
            fmt_money(utilized_by_year.get(year, 0.0)),
        ]
        for year in years
    ]

    charts = [
        line_chart("publication_trend", "Publication Trend",
                   labels, [float(pub_by_year.get(y, 0)) for y in years],
                   name="Publications"),
        line_chart("event_trend", "Event Trend",
                   labels, [float(event_by_year.get(y, 0)) for y in years],
                   name="Events"),
        ReportChart(
            key="budget_trend",
            title="Budget Trend (₹ per project start year)",
            kind=CHART_BAR,
            labels=labels,
            series=[
                ReportChartSeries(name="Approved",
                                  data=[round(approved_by_year.get(y, 0.0), 2) for y in years]),
                ReportChartSeries(name="Utilized",
                                  data=[round(utilized_by_year.get(y, 0.0), 2) for y in years]),
            ],
        ),
        ReportChart(
            key="teaching_load",
            title="Teaching Load (weekly hours per faculty)",
            kind=CHART_BAR,
            labels=load_labels,
            series=[ReportChartSeries(name="Weekly Hours", data=load_hours)],
        ),
        ReportChart(
            key="attendance_trend",
            title="Student Attendance Trend (% per month)",
            kind=CHART_LINE,
            labels=month_labels,
            series=[ReportChartSeries(name="Attendance %", data=month_pcts)],
        ),
    ]

    overall_effective = sum(month_effective.values())
    overall_recorded = sum(month_recorded.values())
    tables = [
        table("year_rollup", "Year-wise Rollup",
              ("Year", "Publications", "Events", "Budget Approved", "Budget Utilized"),
              rollup_rows, [[None] * 5 for _ in rollup_rows]),
    ]
    kpis = [
        kpi("Years Covered", fmt_int(len(years))),
        kpi("Peak Publication Year",
            f"{max(pub_by_year, key=lambda y: pub_by_year[y])} ({fmt_int(max(pub_by_year.values()))})"
            if pub_by_year else "—"),
        kpi("Total Events", fmt_int(sum(event_by_year.values()))),
        kpi("Overall Attendance", fmt_pct(overall_effective, overall_recorded)),
        kpi("Avg Teaching Load",
            f"{round(sum(load_hours) / len(load_hours), 1):g} h/w" if load_hours else "—"),
    ]
    return ReportView(
        kind=KIND,
        title=REPORT_TITLE,
        generated_at=now_iso(),
        applied_filters=applied_filter_strings(filters),
        kpis=kpis,
        tables=tables,
        charts=charts,
    )


class GetAnalyticsReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetAnalyticsReportQuery) -> ReportView:
        return build_analytics_report(
            Snapshot(self._repository), self._repository, query.filters
        )
