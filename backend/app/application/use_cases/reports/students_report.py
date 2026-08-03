"""Use case: Student report (PART 5).

Attendance / assignment / marks / grade summaries per student, composed from
the frozen Teaching module's builders (``build_gradebook`` +
``build_attendance_summary`` conventions): attendance counts follow the
teaching module's documented convention (no record = absent; ``late`` and
``medical_leave`` count toward effective presence), grades come from the
shared gradebook builder so a student report always matches the class
gradebook. Without ``student_id`` the report is the directory-wide overview;
with it, the per-student lens. Computed read — nothing stored.
"""
from __future__ import annotations

from app.application.dtos.reports import ReportView
from app.application.dtos.student import (
    KEY_DEPARTMENT,
    KEY_PROGRAMME,
    KEY_ROLL_NUMBER,
    KEY_SEMESTER,
    KEY_STUDENT_TYPE,
)
from app.application.dtos.teaching import (
    KEY_ATTENDANCE_RECORDS,
    KEY_DEADLINE,
    KEY_IS_LATE,
    KEY_MARKS,
    KEY_MAX_MARKS,
    KEY_SESSION_DATE,
    grade_for,
    parse_json_object,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_students_report import GetStudentsReportQuery
from app.application.use_cases.reports.helpers import (
    Snapshot,
    department_matches,
    fmt_int,
    fmt_number,
    fmt_pct,
    href_for,
    in_filter_window,
    kpi,
    meta_of,
    now_iso,
    table,
    title_case,
)
from app.application.use_cases.teaching.get_gradebook import (
    build_gradebook,
    collect_submissions,
)
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    attendance_sessions_of_class,
    class_id_of_assignment,
    enrolled_students,
    student_of_submission,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import RelationshipKind

KIND = "students"
REPORT_TITLE = "Student Report"

# Effective-presence states (the teaching module's documented convention).
EFFECTIVE_STATES = ("present", "late", "medical_leave")


def _classes_of_student(snapshot: Snapshot, student_id: str) -> list[UniversalObject]:
    """Classes the student carries an ENROLLED_IN edge to (teaching helper
    ``enrolled_students`` inverted — the roster is derived from student edges,
    so the class list is the same set read from the other side)."""
    student = snapshot.get(student_id)
    enrolled = (
        {str(oid) for oid in student.related_ids(RelationshipKind.ENROLLED_IN)}
        if student is not None
        else set()
    )
    out = [cls for cls in snapshot["classes"] if str(cls.id) in enrolled]
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def _attendance_of_student(
    repository: ObjectRepository, student_id: str, class_id: str, filters
) -> dict[str, float | int]:
    sessions = [
        s for s in attendance_sessions_of_class(repository, class_id)
        if in_filter_window(meta_of(s).get(KEY_SESSION_DATE), filters)
    ]
    total = len(sessions)
    effective = 0
    for session in sessions:
        records = parse_json_object(meta_of(session).get(KEY_ATTENDANCE_RECORDS))
        if records.get(student_id, "absent") in EFFECTIVE_STATES:
            effective += 1
    return {"sessions": total, "attended": effective}


def _submissions_of_student(
    repository: ObjectRepository, snapshot: Snapshot, student_id: str
) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for sub in snapshot["submissions"]:
        student = student_of_submission(sub)
        if student is not None and str(student) == student_id:
            out.append(sub)
    return out


def _marks_of_student(
    repository: ObjectRepository, snapshot: Snapshot, student_id: str, filters
) -> dict[str, float]:
    """Assignments statistics for the student (filtered by deadline window)."""
    submissions = _submissions_of_student(repository, snapshot, student_id)
    by_assignment = {
        str(aid): sub
        for sub in submissions
        for aid in sub.related_ids(RelationshipKind.BELONGS_TO)
    }
    assigned = submitted = graded = late = 0
    earned = maximum = 0.0
    for assignment in snapshot["assignments"]:
        meta = meta_of(assignment)
        if not in_filter_window(meta.get(KEY_DEADLINE), filters):
            continue
        # Only assignments of the student's own classes count.
        class_id = class_id_of_assignment(assignment)
        if class_id is None or class_id not in {
            str(c.id) for c in _classes_of_student(snapshot, student_id)
        }:
            continue
        assigned += 1
        sub = by_assignment.get(str(assignment.id))
        if sub is None:
            continue
        sub_meta = meta_of(sub)
        submitted += 1
        if (sub_meta.get(KEY_IS_LATE) or "") == "true":
            late += 1
        marks, maximum_marks = _num(sub_meta.get(KEY_MARKS)), _num(meta.get(KEY_MAX_MARKS))
        if marks is not None:
            graded += 1
            earned += marks
            maximum += maximum_marks or 0.0
    return {
        "assigned": assigned, "submitted": submitted, "graded": graded, "late": late,
        "earned": earned, "maximum": maximum,
    }


def _num(raw) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _grade_of_student(
    repository: ObjectRepository, student_id: str, class_id: str
) -> tuple[float, str] | None:
    roster = enrolled_students(repository, class_id)
    assignments = assignments_of_class(repository, class_id)
    gradebook = build_gradebook(
        roster, assignments, collect_submissions(repository, assignments), class_id=class_id
    )
    for row in gradebook.rows:
        if row.student_id == student_id:
            return row.average_percent, row.grade
    return None


def _overview_row(repository: ObjectRepository, snapshot: Snapshot, student: UniversalObject, filters):
    student_id = str(student.id)
    meta = meta_of(student)
    classes = _classes_of_student(snapshot, student_id)
    sessions_total = attended_total = 0
    for cls in classes:
        att = _attendance_of_student(repository, student_id, str(cls.id), filters)
        sessions_total += att["sessions"]
        attended_total += att["attended"]
    marks = _marks_of_student(repository, snapshot, student_id, filters)
    grades = [g for cls in classes
              if (g := _grade_of_student(repository, student_id, str(cls.id))) is not None]
    if marks["maximum"]:
        overall_pct = round(marks["earned"] / marks["maximum"] * 100, 2)
    elif grades:
        overall_pct = round(sum(g[0] for g in grades) / len(grades), 2)
    else:
        overall_pct = 0.0
    return meta, classes, sessions_total, attended_total, marks, overall_pct


def _profile_view(repository: ObjectRepository, snapshot: Snapshot, student: UniversalObject, filters) -> ReportView:
    student_id = str(student.id)
    classes = _classes_of_student(snapshot, student_id)

    attendance_rows: list[list[str]] = []
    attendance_hrefs: list[list[str | None]] = []
    assignment_rows: list[list[str]] = []
    assignment_hrefs: list[list[str | None]] = []
    marks_rows: list[list[str]] = []
    marks_hrefs: list[list[str | None]] = []
    grade_rows: list[list[str]] = []
    grade_hrefs: list[list[str | None]] = []
    sessions_total = attended_total = 0
    for cls in classes:
        class_id = str(cls.id)
        att = _attendance_of_student(repository, student_id, class_id, filters)
        sessions_total += att["sessions"]
        attended_total += att["attended"]
        attendance_rows.append([
            cls.title, fmt_int(att["sessions"]), fmt_int(att["attended"]),
            fmt_pct(att["attended"], att["sessions"]),
        ])
        attendance_hrefs.append([href_for(cls), None, None, None])

        # Assignment rollup for this class (deadline window applied).
        marks = {"assigned": 0, "submitted": 0, "graded": 0, "late": 0,
                 "earned": 0.0, "maximum": 0.0}
        submissions_by_assignment = {
            str(aid): sub
            for sub in _submissions_of_student(repository, snapshot, student_id)
            for aid in sub.related_ids(RelationshipKind.BELONGS_TO)
        }
        for assignment in assignments_of_class(repository, class_id):
            asg_meta = meta_of(assignment)
            if not in_filter_window(asg_meta.get(KEY_DEADLINE), filters):
                continue
            marks["assigned"] += 1
            sub = submissions_by_assignment.get(str(assignment.id))
            if sub is None:
                continue
            sub_meta = meta_of(sub)
            marks["submitted"] += 1
            if (sub_meta.get(KEY_IS_LATE) or "") == "true":
                marks["late"] += 1
            earned, maximum = _num(sub_meta.get(KEY_MARKS)), _num(asg_meta.get(KEY_MAX_MARKS))
            if earned is not None:
                marks["graded"] += 1
                marks["earned"] += earned
                marks["maximum"] += maximum or 0.0
        assignment_rows.append([
            cls.title, fmt_int(marks["assigned"]), fmt_int(marks["submitted"]),
            fmt_int(marks["graded"]), fmt_int(marks["late"]),
        ])
        assignment_hrefs.append([href_for(cls), None, None, None, None])
        marks_rows.append([
            cls.title,
            fmt_number(marks["earned"]) if marks["graded"] else "—",
            fmt_number(marks["maximum"]) if marks["graded"] else "—",
            fmt_pct(marks["earned"], marks["maximum"]),
        ])
        marks_hrefs.append([href_for(cls), None, None, None])

        grade = _grade_of_student(repository, student_id, class_id)
        grade_rows.append([
            cls.title,
            fmt_number(grade[0]) + "%" if grade else "—",
            grade[1] if grade else "—",
        ])
        grade_hrefs.append([href_for(cls), None, None])

    marks_total = _marks_of_student(repository, snapshot, student_id, filters)
    tables = [
        table("attendance_summary", "Attendance Summary (per class)",
              ("Class", "Sessions", "Attended", "Attendance %"),
              attendance_rows, attendance_hrefs),
        table("assignment_summary", "Assignment Summary (per class)",
              ("Class", "Assigned", "Submitted", "Graded", "Late"),
              assignment_rows, assignment_hrefs),
        table("marks_summary", "Marks Summary (per class)",
              ("Class", "Marks Earned", "Out of", "Percentage"),
              marks_rows, marks_hrefs),
        table("grade_summary", "Grade Summary (per class)",
              ("Class", "Average %", "Grade"),
              grade_rows, grade_hrefs),
    ]
    kpis = [
        kpi("Classes Enrolled", fmt_int(len(classes))),
        kpi("Overall Attendance", fmt_pct(attended_total, sessions_total)),
        kpi("Assignments", f'{fmt_int(marks_total["submitted"])} / {fmt_int(marks_total["assigned"])}'),
        kpi("Graded", fmt_int(marks_total["graded"])),
        kpi("Marks Percentage", fmt_pct(marks_total["earned"], marks_total["maximum"])),
        kpi("Grade (marks-weighted)",
            grade_for(round(marks_total["earned"] / marks_total["maximum"] * 100, 2))
            if marks_total["maximum"] else "—"),
    ]
    return ReportView(
        kind=KIND,
        title=f"{REPORT_TITLE} — {student.title}",
        generated_at=now_iso(),
        applied_filters=applied_filter_strings(filters),
        kpis=kpis,
        tables=tables,
        charts=[],
    )


def _overview_view(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    students = [
        s for s in snapshot["students"]
        if department_matches(meta_of(s).get(KEY_DEPARTMENT), filters.department)
    ]
    students.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    rows: list[list[str]] = []
    hrefs: list[list[str | None]] = []
    below_threshold = 0
    for student in students:
        meta, classes, sessions, attended, _marks, overall_pct = _overview_row(
            repository, snapshot, student, filters
        )
        pct = fmt_pct(attended, sessions)
        if sessions and attended / sessions < 0.75:
            below_threshold += 1
        rows.append([
            student.title,
            meta.get(KEY_ROLL_NUMBER) or "—",
            title_case(meta.get(KEY_STUDENT_TYPE) or "ug"),
            meta.get(KEY_PROGRAMME) or "—",
            meta.get(KEY_DEPARTMENT) or "—",
            str(meta.get(KEY_SEMESTER) or "—"),
            fmt_int(len(classes)),
            pct,
            fmt_number(overall_pct) + "%",
            grade_for(round(overall_pct, 2)) if overall_pct else "—",
        ])
        hrefs.append([href_for(student), None, None, None, None, None, None, None, None, None])
    tables = [
        table("overview", "Student Overview",
              ("Name", "Roll Number", "Type", "Programme", "Department", "Semester",
               "Classes", "Attendance %", "Marks %", "Grade"),
              rows, hrefs),
    ]
    kpis = [
        kpi("Students", fmt_int(len(students))),
        kpi("Below 75% Attendance", fmt_int(below_threshold)),
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


def build_students_report(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    if filters.student_id:
        student = snapshot.get(filters.student_id)
        if student is None or str(filters.student_id) not in {
            str(s.id) for s in snapshot["students"]
        }:
            raise ObjectNotFoundError(f"student '{filters.student_id}' was not found")
        return _profile_view(repository, snapshot, student, filters)
    return _overview_view(repository, snapshot, filters)


class GetStudentsReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetStudentsReportQuery) -> ReportView:
        return build_students_report(
            self._repository, Snapshot(self._repository), query.filters
        )
