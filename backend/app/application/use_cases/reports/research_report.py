"""Use case: Research report (PART 3).

Active projects, completed projects, project timeline, grant summary, budget
summary, project publications and team summary — composed from the frozen
Research module's helpers (``grant_totals``, ``grants_of_project``,
``team_names_of_project``) and the Finance budget composition
(``budget_line_for_project``, so the budget summary matches Finance PART 9
exactly). Computed read — nothing stored.

"Active" = the research dashboard's PROJECT_IN_FLIGHT_STATUSES; "Completed"
= ``completed``/``closed`` (terminal states; the master timeline lists every
project with its actual status).
"""
from __future__ import annotations

from app.application.dtos.reports import ReportView
from app.application.dtos.research import (
    KEY_DEPARTMENT,
    KEY_DURATION,
    KEY_END_DATE,
    KEY_GRANT_NUMBER,
    KEY_LIFECYCLE_STATUS,
    KEY_PROJECT_CODE,
    KEY_START_DATE,
    PROJECT_IN_FLIGHT_STATUSES,
)
from app.application.queries.get_research_report import GetResearchReportQuery
from app.application.use_cases.finance.helpers import budget_line_for_project
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    department_matches,
    fmt_int,
    fmt_money,
    href_for,
    in_filter_window,
    kpi,
    linked_from,
    meta_of,
    now_iso,
    table,
    title_case,
    year_of,
)
from app.application.use_cases.research.helpers import (
    grant_totals,
    grants_of_project,
    team_names_of_project,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository

KIND = "research"
REPORT_TITLE = "Research Report"

# Terminal-done lifecycle states (the research dashboard documents in-flight;
# everything completed/closed lands in the "Completed Projects" table).
COMPLETED_LIFECYCLE_STATUSES = ("completed", "closed")


def _filtered_projects(
    repository: ObjectRepository, snapshot: Snapshot, filters
) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for project in snapshot["projects"]:
        meta = meta_of(project)
        if filters.project_id and str(project.id) != filters.project_id:
            continue
        if filters.grant_id and not any(
            str(grant.id) == filters.grant_id
            for grant in grants_of_project(repository, str(project.id))
        ):
            continue
        if not in_filter_window(meta.get(KEY_START_DATE), filters):
            continue
        if not department_matches(meta.get(KEY_DEPARTMENT), filters.department):
            continue
        out.append(project)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def _project_row(project: UniversalObject, meta: dict[str, str]) -> list[str]:
    return [
        project.title,
        (meta.get(KEY_PROJECT_CODE) or "—"),
        (meta.get(KEY_DEPARTMENT) or "—"),
        (meta.get(KEY_START_DATE) or "—"),
        (meta.get(KEY_END_DATE) or "—"),
        title_case(meta.get(KEY_LIFECYCLE_STATUS) or "draft"),
    ]


def build_research_report(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    projects = _filtered_projects(repository, snapshot, filters)
    grants: list[UniversalObject] = []
    for grant in snapshot["grants"]:
        if filters.grant_id and str(grant.id) != filters.grant_id:
            continue
        if filters.project_id and not any(
            str(funded.id) == str(grant.id)
            for project in projects
            for funded in grants_of_project(repository, str(project.id))
        ):
            continue
        grants.append(grant)
    grants.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))

    active = [p for p in projects if (meta_of(p).get(KEY_LIFECYCLE_STATUS) or "draft") in PROJECT_IN_FLIGHT_STATUSES]
    completed = [p for p in projects if (meta_of(p).get(KEY_LIFECYCLE_STATUS) or "draft") in COMPLETED_LIFECYCLE_STATUSES]

    budget_rows: list[list[str]] = []
    budget_hrefs: list[list[str | None]] = []
    total_approved = total_utilized = total_remaining = 0.0
    for project in projects:
        line = budget_line_for_project(repository, project)
        total_approved += line["approved"] or 0.0
        total_utilized += line["utilized"] or 0.0
        total_remaining += line["remaining"] if line["remaining"] is not None else 0.0
        budget_rows.append([
            project.title,
            fmt_money(line["approved"]),
            fmt_money(line["released"]),
            fmt_money(line["utilized"]),
            fmt_money(line["remaining"]),
            fmt_int(line["proposals"]),
            fmt_money(line["spent"]),
        ])
        budget_hrefs.append([href_for(project), None, None, None, None, None, None])

    timeline = sorted(projects, key=lambda obj: (meta_of(obj).get(KEY_START_DATE) or "", obj.title.casefold()))
    year_buckets: dict[str, int] = {}
    for project in projects:
        year = year_of(meta_of(project).get(KEY_START_DATE))
        if year is not None:
            label = str(year)
            year_buckets[label] = year_buckets.get(label, 0) + 1

    grant_rows: list[list[str]] = []
    grant_hrefs: list[list[str | None]] = []
    for grant in grants:
        meta = meta_of(grant)
        totals = grant_totals(repository, grant)
        grant_rows.append([
            grant.title,
            (meta.get(KEY_GRANT_NUMBER) or "—"),
            fmt_money(totals["approved"]),
            fmt_money(totals["released"]),
            fmt_money(totals["utilized"]),
            fmt_money(totals["remaining"]),
        ])
        grant_hrefs.append([href_for(grant), None, None, None, None, None])

    publication_rows: list[list[str]] = []
    publication_hrefs: list[list[str | None]] = []
    team_rows: list[list[str]] = []
    team_hrefs: list[list[str | None]] = []
    for project in projects:
        pubs = linked_from(snapshot, "publications", str(project.id))
        publication_rows.append([
            project.title,
            fmt_int(len(pubs)),
            "; ".join(pub.title for pub in pubs) or "—",
        ])
        publication_hrefs.append([
            href_for(project), None, href_for(pubs[0]) if pubs else None,
        ])
        team_rows.append([
            project.title,
            team_names_of_project(repository, str(project.id)) or "—",
        ])
        team_hrefs.append([href_for(project), None])

    tables = [
        table("active_projects", "Active Projects",
              ("Title", "Code", "Department", "Start", "End", "Status"),
              [_project_row(p, meta_of(p)) for p in active],
              [[href_for(p), None, None, None, None, None] for p in active]),
        table("completed_projects", "Completed Projects",
              ("Title", "Code", "Department", "Start", "End", "Status"),
              [_project_row(p, meta_of(p)) for p in completed],
              [[href_for(p), None, None, None, None, None] for p in completed]),
        table("timeline", "Project Timeline",
              ("Title", "Start", "End", "Duration", "Status"),
              [[p.title,
                meta_of(p).get(KEY_START_DATE) or "—",
                meta_of(p).get(KEY_END_DATE) or "—",
                meta_of(p).get(KEY_DURATION) or "—",
                title_case(meta_of(p).get(KEY_LIFECYCLE_STATUS) or "draft")]
               for p in timeline],
              [[href_for(p), None, None, None, None] for p in timeline]),
        table("grant_summary", "Grant Summary",
              ("Grant", "Grant Number", "Approved", "Released", "Utilized", "Remaining"),
              grant_rows, grant_hrefs),
        table("budget_summary", "Budget Summary (per Project)",
              ("Project", "Approved", "Grants Released", "Utilized", "Remaining",
               "Procurements", "Procurement Spend"),
              budget_rows, budget_hrefs),
        table("project_publications", "Project Publications",
              ("Project", "Publications", "Titles"),
              publication_rows, publication_hrefs),
        table("team_summary", "Team Summary",
              ("Project", "Team"),
              team_rows, team_hrefs),
    ]

    year_labels = sorted(year_buckets)
    charts = [
        bar_chart("starts_per_year", "Projects by Start Year",
                  year_labels, [float(year_buckets[y]) for y in year_labels],
                  name="Projects"),
    ]

    kpis = [
        kpi("Total Projects", fmt_int(len(projects))),
        kpi("Active Projects", fmt_int(len(active))),
        kpi("Completed Projects", fmt_int(len(completed))),
        kpi("Grants", fmt_int(len(grants))),
        kpi("Budget Approved", fmt_money(total_approved)),
        kpi("Budget Utilized", fmt_money(total_utilized)),
        kpi("Budget Remaining", fmt_money(total_remaining)),
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


class GetResearchReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetResearchReportQuery) -> ReportView:
        return build_research_report(
            self._repository, Snapshot(self._repository), query.filters
        )
