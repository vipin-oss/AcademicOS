"""Use case: Committee report (PART 9).

Meetings / attendance / action items / pending / completed lenses over the
frozen Committees module's data, composing its own collectors
(``meetings_of_committee``, ``actions_of_meeting``,
``committee_action_counts``) so participation semantics stay single-sourced.
Attendance aggregates each meeting's attendance rows (present / total).
Computed read — nothing stored.
"""
from __future__ import annotations

from app.application.dtos.committee import (
    KEY_ACTION_STATUS,
    KEY_ASSIGNED_NAME,
    KEY_ATTENDANCE,
    KEY_COMMITTEE_TYPE,
    KEY_DUE_DATE,
    KEY_MEETING_DATE,
    KEY_MEETING_NUMBER,
    KEY_MEMBERS,
    KEY_MODE,
    KEY_PRIORITY,
)
from app.application.dtos.reports import ReportView
from app.application.queries.get_committees_report import GetCommitteesReportQuery
from app.application.use_cases.committees.helpers import (
    actions_of_meeting,
)
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    fmt_int,
    fmt_pct,
    href_for,
    in_filter_window,
    kpi,
    meta_of,
    now_iso,
    parse_json_list,
    table,
    title_case,
    year_of,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import RelationshipKind

KIND = "committees"
REPORT_TITLE = "Committee Report"

PRESENT_STATES = ("present",)


def _meeting_committee_ids(meeting: UniversalObject) -> set[str]:
    return {
        str(rel.target)
        for rel in meeting.relationships
        if rel.kind is RelationshipKind.BELONGS_TO
    }


def _filtered_committees(snapshot: Snapshot, filters) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for committee in snapshot["committees"]:
        if filters.committee_id and str(committee.id) != filters.committee_id:
            continue
        if filters.faculty_id:
            members = parse_json_list(meta_of(committee).get(KEY_MEMBERS))
            if not any(
                isinstance(row, dict) and str(row.get("faculty_id") or "") == filters.faculty_id
                for row in members
            ):
                continue
        out.append(committee)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def build_committees_report(
    repository: ObjectRepository, snapshot: Snapshot, filters
) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    scope = _filtered_committees(snapshot, filters)
    scope_ids = {str(c.id) for c in scope}

    meeting_rows: list[list[str]] = []
    meeting_hrefs: list[list[str | None]] = []
    attendance_rows: list[list[str]] = []
    action_rows: list[list[str]] = []
    pending_rows: list[list[str]] = []
    completed_rows: list[list[str]] = []
    committee_rows: list[list[str]] = []
    committee_hrefs: list[list[str | None]] = []
    meetings_seen = 0
    present_total = attendance_total = 0
    year_counts: dict[str, int] = {}
    action_counts: dict[str, dict[str, int]] = {str(c.id): {"pending": 0, "completed": 0} for c in scope}
    meeting_counts: dict[str, int] = {str(c.id): 0 for c in scope}

    committee_by_id = {str(c.id): c for c in snapshot["committees"]}

    meetings = [
        m for m in snapshot["meetings"]
        if _meeting_committee_ids(m) & scope_ids
        and in_filter_window(meta_of(m).get(KEY_MEETING_DATE), filters)
    ]
    meetings.sort(key=lambda o: (meta_of(o).get(KEY_MEETING_DATE) or "", o.title.casefold()))

    for meeting in meetings:
        meta = meta_of(meeting)
        meetings_seen += 1
        committee = next(
            (committee_by_id[cid] for cid in _meeting_committee_ids(meeting) if cid in scope_ids),
            None,
        )
        if committee is not None:
            meeting_counts[str(committee.id)] = meeting_counts.get(str(committee.id), 0) + 1
        year = year_of(meta.get(KEY_MEETING_DATE))
        if year is not None:
            key = str(year)
            year_counts[key] = year_counts.get(key, 0) + 1
        attendance = [
            row for row in parse_json_list(meta.get(KEY_ATTENDANCE))
            if isinstance(row, dict)
        ]
        present = sum(1 for row in attendance if (row.get("status") or "") in PRESENT_STATES)
        present_total += present
        attendance_total += len(attendance)
        meeting_rows.append([
            meeting.title,
            meta.get(KEY_MEETING_NUMBER) or "—",
            committee.title if committee else "—",
            meta.get(KEY_MEETING_DATE) or "—",
            title_case(meta.get(KEY_MODE) or "offline"),
            fmt_int(len(attendance)),
            fmt_int(present),
            fmt_pct(present, len(attendance)),
        ])
        meeting_hrefs.append([href_for(meeting), None,
                              href_for(committee) if committee else None, None, None, None, None, None])
        attendance_rows.append([
            meeting.title,
            meta.get(KEY_MEETING_DATE) or "—",
            fmt_int(present),
            fmt_int(len(attendance)),
            fmt_pct(present, len(attendance)),
        ])
        for action in actions_of_meeting(repository, str(meeting.id)):
            action_meta = meta_of(action)
            status = action_meta.get(KEY_ACTION_STATUS) or "pending"
            row = [
                action.title,
                meeting.title,
                str(action_meta.get(KEY_ASSIGNED_NAME) or "—"),
                str(action_meta.get(KEY_DUE_DATE) or "—"),
                title_case(str(action_meta.get(KEY_PRIORITY) or "medium")),
                title_case(str(status)),
            ]
            action_rows.append(row)
            if committee is not None:
                bucket = action_counts.setdefault(
                    str(committee.id), {"pending": 0, "completed": 0}
                )
                bucket["completed" if status == "done" else "pending"] += 1
            if status == "done":
                completed_rows.append(row)
            else:
                pending_rows.append(row)

    pending_total = len(pending_rows)
    completed_total = len(completed_rows)

    for committee in scope:
        counts = action_counts.get(str(committee.id), {"pending": 0, "completed": 0})
        committee_rows.append([
            committee.title,
            title_case(meta_of(committee).get(KEY_COMMITTEE_TYPE)),
            fmt_int(meeting_counts.get(str(committee.id), 0)),
            fmt_int(counts["pending"]),
            fmt_int(counts["completed"]),
        ])
        committee_hrefs.append([href_for(committee), None, None, None, None])

    year_labels = sorted(year_counts)
    tables = [
        table("committee_summary", "Committee Summary",
              ("Committee", "Type", "Meetings", "Pending Actions", "Completed Actions"),
              committee_rows, committee_hrefs),
        table("meetings", "Meetings",
              ("Meeting", "Number", "Committee", "Date", "Mode", "Invited", "Present", "Attendance %"),
              meeting_rows, meeting_hrefs),
        table("attendance", "Meeting Attendance",
              ("Meeting", "Date", "Present", "Invited", "Attendance %"),
              attendance_rows, [[None] * 5 for _ in attendance_rows]),
        table("action_items", "Action Items",
              ("Action", "Meeting", "Assigned To", "Due Date", "Priority", "Status"),
              action_rows, [[None] * 6 for _ in action_rows]),
        table("pending_actions", "Pending Actions",
              ("Action", "Meeting", "Assigned To", "Due Date", "Priority", "Status"),
              pending_rows, [[None] * 6 for _ in pending_rows]),
        table("completed_actions", "Completed Actions",
              ("Action", "Meeting", "Assigned To", "Due Date", "Priority", "Status"),
              completed_rows, [[None] * 6 for _ in completed_rows]),
    ]
    charts = [
        bar_chart("meetings_per_year", "Meetings per Year",
                  year_labels, [float(year_counts[y]) for y in year_labels],
                  name="Meetings"),
        bar_chart("actions", "Action Items",
                  ["Pending", "Completed"], [float(pending_total), float(completed_total)],
                  name="Actions"),
    ]
    kpis = [
        kpi("Committees", fmt_int(len(scope))),
        kpi("Meetings", fmt_int(meetings_seen)),
        kpi("Overall Attendance", fmt_pct(present_total, attendance_total)),
        kpi("Action Items", fmt_int(pending_total + completed_total)),
        kpi("Pending Actions", fmt_int(pending_total)),
        kpi("Completed Actions", fmt_int(completed_total)),
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


class GetCommitteesReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCommitteesReportQuery) -> ReportView:
        return build_committees_report(
            self._repository, Snapshot(self._repository), query.filters
        )
