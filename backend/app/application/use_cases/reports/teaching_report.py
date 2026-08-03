"""Use case: Teaching report (PART 6).

Class summary / attendance percentage / assignment statistics / gradebook
summary per class, composed from the frozen Teaching module's builders
(``build_gradebook`` + the attendance convention documented on
``build_attendance_summary``): no record = absent; ``late`` and
``medical_leave`` count toward effective presence. PART 12 year/date-range
filters scope the attendance sessions and assignment deadlines inside each
class; ``faculty_id`` scopes classes to those TAUGHT_BY that member.
Computed read — nothing stored.
"""
from __future__ import annotations

from app.application.dtos.reports import ReportView
from app.application.dtos.teaching import (
    KEY_ATTENDANCE_RECORDS,
    KEY_COURSE_CODE,
    KEY_CREDITS,
    KEY_DEADLINE,
    KEY_MARKS,
    KEY_MAX_MARKS,
    KEY_PROGRAMME,
    KEY_SEMESTER,
    KEY_SESSION,
    KEY_SESSION_DATE,
    parse_json_object,
)
from app.application.queries.get_teaching_report import GetTeachingReportQuery
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    fmt_int,
    href_for,
    in_filter_window,
    kpi,
    meta_of,
    now_iso,
    table,
)
from app.application.use_cases.reports.students_report import EFFECTIVE_STATES
from app.application.use_cases.teaching.get_gradebook import (
    build_gradebook,
    collect_submissions,
)
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    attendance_sessions_of_class,
    enrolled_students,
    submissions_of_assignment,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import RelationshipKind

KIND = "teaching"
REPORT_TITLE = "Teaching Report"


def _num(raw) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _class_stats(repository: ObjectRepository, cls: UniversalObject, filters) -> dict:
    class_id = str(cls.id)
    roster = enrolled_students(repository, class_id)
    sessions = [
        s for s in attendance_sessions_of_class(repository, class_id)
        if in_filter_window(meta_of(s).get(KEY_SESSION_DATE), filters)
    ]
    effective = recorded = 0
    for session in sessions:
        records = parse_json_object(meta_of(session).get(KEY_ATTENDANCE_RECORDS))
        for student in roster:
            state = records.get(str(student.id), "absent")  # no record = absent
            recorded += 1
            if state in EFFECTIVE_STATES:
                effective += 1

    assignments = [
        a for a in assignments_of_class(repository, class_id)
        if in_filter_window(meta_of(a).get(KEY_DEADLINE), filters)
    ]
    max_marks_by_assignment = {
        str(a.id): _num(meta_of(a).get(KEY_MAX_MARKS)) or 0.0 for a in assignments
    }
    submissions = [
        sub
        for assignment in assignments
        for sub in submissions_of_assignment(repository, str(assignment.id))
    ]
    graded = [s for s in submissions if _num(meta_of(s).get(KEY_MARKS)) is not None]
    earned = sum(_num(meta_of(s).get(KEY_MARKS)) or 0.0 for s in graded)
    maximum = 0.0
    for sub in graded:
        for oid in sub.related_ids(RelationshipKind.BELONGS_TO):
            maximum += max_marks_by_assignment.get(str(oid), 0.0)

    gradebook = build_gradebook(
        roster, assignments, collect_submissions(repository, assignments),
        class_id=class_id,
    )
    graded_rows = [row for row in gradebook.rows if row.cells]
    averages = [row.average_percent for row in graded_rows]
    class_average = round(sum(averages) / len(averages), 2) if averages else None
    return {
        "students": len(roster),
        "sessions": len(sessions),
        "att_effective": effective,
        "att_recorded": recorded,
        "attendance_pct": round(effective / recorded * 100, 2) if recorded else None,
        "assignments": len(assignments),
        "submissions": len(submissions),
        "graded": len(graded),
        "avg_score_pct": round(earned / maximum * 100, 2) if maximum else None,
        "class_average_pct": class_average,
        "grades": len(graded_rows),
    }


def _filtered_classes(snapshot: Snapshot, filters) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for cls in snapshot["classes"]:
        if filters.faculty_id and not any(
            rel.kind is RelationshipKind.TAUGHT_BY and str(rel.target) == filters.faculty_id
            for rel in cls.relationships
        ):
            continue
        out.append(cls)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def build_teaching_report(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    classes = _filtered_classes(snapshot, filters)

    summary_rows: list[list[str]] = []
    summary_hrefs: list[list[str | None]] = []
    attendance_rows: list[list[str]] = []
    assignment_rows: list[list[str]] = []
    gradebook_rows: list[list[str]] = []
    labels_attendance: list[str] = []
    data_attendance: list[float] = []
    labels_assignments: list[str] = []
    data_assignments: list[float] = []
    totals = {"students": set(), "sessions": 0, "assignments": 0,
              "submissions": 0, "att_effective": 0.0, "att_recorded": 0}

    for cls in classes:
        meta = meta_of(cls)
        stats = _class_stats(repository, cls, filters)
        totals["students"].update(
            str(s.id) for s in enrolled_students(repository, str(cls.id))
        )
        totals["sessions"] += stats["sessions"]
        totals["assignments"] += stats["assignments"]
        totals["submissions"] += stats["submissions"]
        totals["att_effective"] += stats["att_effective"]
        totals["att_recorded"] += stats["att_recorded"]

        summary_rows.append([
            meta.get(KEY_COURSE_CODE) or "—",
            cls.title,
            meta.get(KEY_PROGRAMME) or "—",
            str(meta.get(KEY_SEMESTER) or "—"),
            meta.get(KEY_SESSION) or "—",
            str(meta.get(KEY_CREDITS) or "—"),
            fmt_int(stats["students"]),
        ])
        summary_hrefs.append([None, href_for(cls), None, None, None, None, None])
        attendance_rows.append([
            cls.title, fmt_int(stats["sessions"]),
            f'{stats["attendance_pct"]:g}%' if stats["attendance_pct"] is not None else "—",
        ])
        assignment_rows.append([
            cls.title, fmt_int(stats["assignments"]), fmt_int(stats["submissions"]),
            fmt_int(stats["graded"]),
            f'{stats["avg_score_pct"]:g}%' if stats["avg_score_pct"] is not None else "—",
        ])
        gradebook_rows.append([
            cls.title,
            f'{stats["class_average_pct"]:g}%' if stats["class_average_pct"] is not None else "—",
            fmt_int(stats["grades"]),
        ])
        if stats["attendance_pct"] is not None:
            labels_attendance.append(cls.title)
            data_attendance.append(stats["attendance_pct"])
        labels_assignments.append(cls.title)
        data_assignments.append(float(stats["assignments"]))

    attendance_pct_all: float | None = None
    if totals["att_recorded"]:
        attendance_pct_all = round(totals["att_effective"] / totals["att_recorded"] * 100, 2)

    tables = [
        table("class_summary", "Class Summary",
              ("Course Code", "Title", "Programme", "Semester", "Session", "Credits", "Students"),
              summary_rows, summary_hrefs),
        table("attendance", "Attendance Percentage (per class)",
              ("Class", "Sessions Held", "Attendance %"),
              attendance_rows, [[None, None, None] for _ in attendance_rows]),
        table("assignments", "Assignment Statistics (per class)",
              ("Class", "Assignments", "Submissions", "Graded", "Avg Score %"),
              assignment_rows, [[None, None, None, None, None] for _ in assignment_rows]),
        table("gradebook", "Gradebook Summary (per class)",
              ("Class", "Class Average %", "Students Graded"),
              gradebook_rows, [[None, None, None] for _ in gradebook_rows]),
    ]
    charts = [
        bar_chart("attendance_by_class", "Attendance % by Class",
                  labels_attendance, data_attendance, name="Attendance %"),
        bar_chart("assignments_by_class", "Assignments by Class",
                  labels_assignments, data_assignments, name="Assignments"),
    ]
    kpis = [
        kpi("Classes", fmt_int(len(classes))),
        kpi("Students Enrolled", fmt_int(len(totals["students"]))),
        kpi("Sessions Held", fmt_int(totals["sessions"])),
        kpi("Overall Attendance",
            f"{attendance_pct_all:g}%" if attendance_pct_all is not None else "—"),
        kpi("Assignments", fmt_int(totals["assignments"])),
        kpi("Submissions", fmt_int(totals["submissions"])),
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


class GetTeachingReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetTeachingReportQuery) -> ReportView:
        return build_teaching_report(
            self._repository, Snapshot(self._repository), query.filters
        )
