"""Use case: Faculty report (PART 4).

Per-member academic profile composed from the frozen Faculty module's own
edge helpers (``research_projects_of_faculty``, ``grants_of_projects``,
``supervision_of_faculty``, ``classes_of_faculty``) plus AUTHORED_BY scans
(the ``publications_count_of_faculty`` predicate, returning the Objects) and
committee membership / event links. Without ``faculty_id`` the report is the
directory-wide overview table; with it, the full profile lens of one member.
Computed read — nothing stored.
"""
from __future__ import annotations

from app.application.dtos.committee import KEY_MEMBERS
from app.application.dtos.faculty import (
    KEY_DEPARTMENT,
    KEY_DESIGNATION,
    KEY_EMAIL,
    KEY_EMPLOYEE_ID,
    KEY_QUALIFICATION,
    KEY_SCHOOL,
    KEY_SPECIALIZATION,
)
from app.application.dtos.publication import (
    KEY_JOURNAL,
    KEY_PUBLICATION_TYPE,
    KEY_YEAR,
)
from app.application.dtos.reports import ReportView
from app.application.queries.get_faculty_report import GetFacultyReportQuery
from app.application.use_cases.faculty.helpers import (
    classes_of_faculty,
    grants_of_projects,
    research_projects_of_faculty,
    supervision_of_faculty,
)
from app.application.use_cases.reports.helpers import (
    Snapshot,
    department_matches,
    fmt_int,
    fmt_number,
    href_for,
    in_filter_window,
    kpi,
    linked_from,
    meta_of,
    now_iso,
    parse_json_list,
    table,
    year_of,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import RelationshipKind

KIND = "faculty"
REPORT_TITLE = "Faculty Report"


def _publications_of(snapshot: Snapshot, faculty_id: str) -> list[UniversalObject]:
    """AUTHORED_BY → faculty (publications module edge) — same predicate as
    ``publications_count_of_faculty``, returning the Objects."""
    pubs = [
        pub
        for pub in snapshot["publications"]
        if any(
            rel.kind is RelationshipKind.AUTHORED_BY and str(rel.target) == faculty_id
            for rel in pub.relationships
        )
    ]
    pubs.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return pubs


def _committees_of(snapshot: Snapshot, faculty_id: str) -> list[UniversalObject]:
    """Committees whose members rows carry this member — the persisted
    whitelist key is ``faculty_id`` (committee dtos, PART 2)."""
    out: list[UniversalObject] = []
    for committee in snapshot["committees"]:
        rows = parse_json_list(meta_of(committee).get(KEY_MEMBERS))
        if any(
            isinstance(row, dict) and str(row.get("faculty_id") or "") == faculty_id
            for row in rows
        ):
            out.append(committee)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def _counts(repository: ObjectRepository, snapshot: Snapshot, member: UniversalObject) -> dict[str, int | float]:
    faculty_id = str(member.id)
    _, projects = research_projects_of_faculty(repository, member)
    grants = grants_of_projects(repository, set(projects))
    supervision = supervision_of_faculty(repository, faculty_id)
    classes, weekly_hours = classes_of_faculty(repository, faculty_id)
    return {
        "publications": len(_publications_of(snapshot, faculty_id)),
        "projects": len(projects),
        "grants": len(grants),
        "students": len(supervision["current"]),
        "classes": len(classes),
        "weekly_hours": weekly_hours,
        "committees": len(_committees_of(snapshot, faculty_id)),
        "events": len(linked_from(snapshot, "events", faculty_id)),
    }


def _profile_view(
    repository: ObjectRepository, snapshot: Snapshot, member: UniversalObject, filters
) -> ReportView:
    meta = meta_of(member)
    faculty_id = str(member.id)
    counts = _counts(repository, snapshot, member)

    # Month precision unavailable on year-only publications — the year window
    # rule documented in the publications report applies here too.
    pubs = [
        pub for pub in _publications_of(snapshot, faculty_id)
        if _year_window_ok(meta_of(pub), filters)
    ]

    _, projects_map = research_projects_of_faculty(repository, member)
    projects = sorted(projects_map.values(), key=lambda o: (o.title.casefold(), str(o.id)))
    grants = grants_of_projects(repository, {str(p.id) for p in projects})
    supervision = supervision_of_faculty(repository, faculty_id)
    classes, weekly_hours = classes_of_faculty(repository, faculty_id)
    committees = _committees_of(snapshot, faculty_id)
    events = linked_from(snapshot, "events", faculty_id)

    def _windowed(objs: list[UniversalObject], date_key: str) -> list[UniversalObject]:
        return [o for o in objs if in_filter_window(meta_of(o).get(date_key), filters)]

    projects = _windowed(projects, "start_date")
    events = _windowed(events, "start_date")

    profile_rows = [
        ["Name", member.title],
        ["Employee ID", meta.get(KEY_EMPLOYEE_ID) or "—"],
        ["Designation", meta.get(KEY_DESIGNATION) or "—"],
        ["Department", meta.get(KEY_DEPARTMENT) or "—"],
        ["School", meta.get(KEY_SCHOOL) or "—"],
        ["Email", meta.get(KEY_EMAIL) or "—"],
        ["Qualification", meta.get(KEY_QUALIFICATION) or "—"],
        ["Specialization", meta.get(KEY_SPECIALIZATION) or "—"],
    ]
    tables = [
        table("profile", "Faculty Profile", ("Field", "Value"), profile_rows,
              [[None], [None], [None], [None], [None], [None], [None], [None]]),
        table("publications", "Publications", ("Title", "Type", "Year", "Journal"),
              [[p.title,
                (meta_of(p).get(KEY_PUBLICATION_TYPE) or "—"),
                str(y) if (y := year_of(meta_of(p).get(KEY_YEAR))) is not None else "—",
                (meta_of(p).get(KEY_JOURNAL) or "—")] for p in pubs],
              [[href_for(p), None, None, None] for p in pubs]),
        table("projects", "Projects", ("Title", "Status", "Start", "End"),
              [[p.title,
                (meta_of(p).get("lifecycle_status") or "—"),
                (meta_of(p).get("start_date") or "—"),
                (meta_of(p).get("end_date") or "—")] for p in projects],
              [[href_for(p), None, None, None] for p in projects]),
        table("grants", "Grants", ("Title", "Grant Number", "Amount"),
              [[g["title"],
                (meta_of(g_obj).get("grant_number") or "—")
                if (g_obj := snapshot.get(g["id"])) is not None else "—",
                (meta_of(g_obj).get("amount") or "—")
                if (g_obj := snapshot.get(g["id"])) is not None else "—"]
               for g in grants],
              [[f"/research/grants/{g['id']}", None, None] for g in grants]),
        table("supervision", "Students Supervised (current)", ("Student", "Link"),
              [[s["title"], "—"] for s in supervision["current"]],
              [[f"/students/{s['id']}", None] for s in supervision["current"]]),
        table("teaching", "Teaching (classes)", ("Class", "Course Code", "Semester", "Weekly Hours"),
              [[c["title"], c.get("course_code") or "—",
                str(c["semester"]) if c.get("semester") is not None else "—",
                fmt_number(c.get("weekly_hours") or 0.0)] for c in classes],
              [[f"/teaching/classes/{c['id']}", None, None, None] for c in classes]),
        table("events", "Events", ("Title", "Type", "Start"),
              [[e.title,
                (meta_of(e).get("event_type") or "—"),
                (meta_of(e).get("start_date") or "—")] for e in events],
              [[href_for(e), None, None] for e in events]),
        table("committees", "Committees", ("Name", "Type"),
              [[c.title, (meta_of(c).get("committee_type") or "—")] for c in committees],
              [[href_for(c), None] for c in committees]),
    ]
    kpis = [
        kpi("Publications", fmt_int(counts["publications"])),
        kpi("Projects", fmt_int(counts["projects"])),
        kpi("Grants", fmt_int(counts["grants"])),
        kpi("Students Supervised", fmt_int(counts["students"])),
        kpi("Classes", fmt_int(counts["classes"])),
        kpi("Weekly Teaching Hours", fmt_number(counts["weekly_hours"])),
        kpi("Committees", fmt_int(counts["committees"])),
        kpi("Events", fmt_int(counts["events"])),
    ]
    return ReportView(
        kind=KIND,
        title=f"{REPORT_TITLE} — {member.title}",
        generated_at=now_iso(),
        applied_filters=applied_filter_strings(filters),
        kpis=kpis,
        tables=tables,
        charts=[],
    )


def _year_window_ok(meta: dict[str, str], filters) -> bool:
    if filters.year is not None:
        return year_of(meta.get(KEY_YEAR) or meta.get("date")) == filters.year
    if not (filters.date_from or filters.date_to):
        return True
    year = year_of(meta.get(KEY_YEAR) or meta.get("date"))
    if year is None:
        return False
    from_year = year_of(filters.date_from)
    to_year = year_of(filters.date_to)
    if from_year is not None and year < from_year:
        return False
    return not (to_year is not None and year > to_year)


def _overview_view(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    members = [
        m for m in snapshot["faculty"]
        if department_matches(meta_of(m).get("department"), filters.department)
    ]
    members.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    rows: list[list[str]] = []
    hrefs: list[list[str | None]] = []
    totals = {"publications": 0, "projects": 0, "classes": 0}
    for member in members:
        meta = meta_of(member)
        counts = _counts(repository, snapshot, member)
        totals["publications"] += counts["publications"]
        totals["projects"] += counts["projects"]
        totals["classes"] += counts["classes"]
        rows.append([
            member.title,
            meta.get(KEY_DESIGNATION) or "—",
            meta.get(KEY_DEPARTMENT) or "—",
            fmt_int(counts["publications"]),
            fmt_int(counts["projects"]),
            fmt_int(counts["grants"]),
            fmt_int(counts["classes"]),
            fmt_number(counts["weekly_hours"]),
            fmt_int(counts["committees"]),
            fmt_int(counts["events"]),
        ])
        hrefs.append([href_for(member), None, None, None, None, None, None, None, None, None])
    tables = [
        table("overview", "Faculty Overview",
              ("Name", "Designation", "Department", "Publications", "Projects", "Grants",
               "Classes", "Weekly Hours", "Committees", "Events"),
              rows, hrefs),
    ]
    kpis = [
        kpi("Faculty Members", fmt_int(len(members))),
        kpi("Authored Publications", fmt_int(totals["publications"])),
        kpi("Projects Led / In Team", fmt_int(totals["projects"])),
        kpi("Classes Taught", fmt_int(totals["classes"])),
    ]
    return ReportView(
        kind=KIND,
        title=REPORT_TITLE,
        generated_at=now_iso(),
        applied_filters=applied_filter_strings(filters),
        kpis=kpis,
        tables=tables,
        charts=[],
    )


def build_faculty_report(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    if filters.faculty_id:
        member = snapshot.get(filters.faculty_id)
        if member is None or member not in snapshot["faculty"]:
            from app.application.exceptions import ObjectNotFoundError

            raise ObjectNotFoundError(f"faculty '{filters.faculty_id}' was not found")
        return _profile_view(repository, snapshot, member, filters)
    return _overview_view(repository, snapshot, filters)


class GetFacultyReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetFacultyReportQuery) -> ReportView:
        return build_faculty_report(
            self._repository, Snapshot(self._repository), query.filters
        )
