"""Unit tests for the Reports & Analytics use cases (no framework deps).

Mirrors ``test_events_use_cases.py`` / ``test_finance_use_cases.py``: an
in-memory ``ObjectRepository`` fabricates a small cross-module world and the
report builders run against it — verifying PART 1..11 outputs are computed
from the frozen modules' data (never re-stored).
"""
from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.application.dtos.reports import ReportFilters
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.queries.export_report import ExportReportQuery
from app.application.queries.get_reports_dashboard import GetReportsDashboardQuery
from app.application.use_cases.reports.analytics_report import build_analytics_report
from app.application.use_cases.reports.committees_report import build_committees_report
from app.application.use_cases.reports.events_report import build_events_report
from app.application.use_cases.reports.export_report import ExportReportUseCase
from app.application.use_cases.reports.faculty_report import build_faculty_report
from app.application.use_cases.reports.finance_report import build_finance_report
from app.application.use_cases.reports.get_dashboard import GetReportsDashboardUseCase
from app.application.use_cases.reports.helpers import Snapshot
from app.application.use_cases.reports.publications_report import (
    build_publications_report,
)
from app.application.use_cases.reports.research_report import build_research_report
from app.application.use_cases.reports.students_report import build_students_report
from app.application.use_cases.reports.teaching_report import build_teaching_report
from app.application.validators.reports import assert_valid_filters
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[str(entity.id)] = entity

    def get_by_id(self, id) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id) -> bool:
        return str(id) in self._store

    def delete(self, id) -> None:
        self._store.pop(str(id), None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id, kind=None) -> list:
        obj = self._store.get(str(object_id))
        return [] if obj is None else obj.related_ids(kind)
    def find_inbound(
        self, object_id: ObjectId, kind=None
    ) -> list[ObjectId]:
        return [
            o.id
            for o in self._store.values()
            if any(r.target == object_id and (kind is None or r.kind == kind) for r in o.relationships)
        ]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        if page < 1:
            raise ValueError("page must be >= 1.")
        if page_size < 0:
            raise ValueError("page_size must be >= 0.")
        if sort_by is not None and sort_by not in (
            "id", "object_type", "title", "title_ci", "status", "version",
        ):
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
        if order not in ("asc", "desc"):
            raise ValueError(f"Unsupported order: {order!r}")

        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    (value := o.metadata.get_value(metadata_key)) is not None
                    and (metadata_value is None or value == metadata_value)
                )
            )
        ]
        effective_sort = sort_by if sort_by is not None else ("id" if page_size > 0 else None)
        if effective_sort is not None:
            reverse = order == "desc"
            if effective_sort == "id":
                items.sort(key=lambda o: str(o.id), reverse=reverse)
            elif effective_sort == "object_type":
                items.sort(key=lambda o: o.object_type.value, reverse=reverse)
            elif effective_sort in ("title", "title_ci"):
                items.sort(key=lambda o: o.title, reverse=reverse)
            elif effective_sort == "status":
                items.sort(key=lambda o: o.status.value, reverse=reverse)
            elif effective_sort == "version":
                items.sort(key=lambda o: o.version, reverse=reverse)
        if page_size > 0:
            start = (page - 1) * page_size
            items = items[start : start + page_size]
        return items

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        return len(
            self.find(
                object_type=object_type,
                status=status,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            )
        )


    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


# ---------------------------------------------------------------------------
# Fabrication helpers (mirror the other suites' style)
# ---------------------------------------------------------------------------
def _meta_entries(**pairs: str) -> tuple:
    return tuple(
        MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        for key, value in pairs.items()
    )


def _make(repo: InMemoryObjectRepository, kind: ObjectType, title: str,
          links: list[tuple[ObjectId, RelationshipKind]] | None = None,
          **meta: str) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=kind, title=title, created_by="registrar:1",
        status=ObjectStatus.ACTIVE, metadata=Metadata(entries=_meta_entries(**meta)),
    )
    for target, rel_kind in links or []:
        obj.add_relationship(target, rel_kind, actor="registrar:1")
    repo.save(obj)
    obj.pop_domain_events()
    return obj


@pytest.fixture()
def world() -> InMemoryObjectRepository:
    """One small cross-module world (all entities fabricated directly)."""
    repo = InMemoryObjectRepository()

    faculty = _make(repo, ObjectType.FACULTY, "Dr. Meera Krishnan",
                    designation="Professor", department="Mathematics",
                    employee_id="EMP-1", email="meera@univ.edu")
    student = _make(repo, ObjectType.STUDENT, "Asha Verma",
                    student_type="pg", roll_number="PG-01", department="Mathematics",
                    programme="MSc Mathematics", semester="2")
    project = _make(repo, ObjectType.RESEARCH_PROJECT, "Graph Frontiers",
                    department="Mathematics", project_code="PRJ-1",
                    lifecycle_status="active", start_date="2024-04-01",
                    end_date="2027-03-31", budget_approved="500000",
                    budget_utilized="120000")
    grant = _make(repo, ObjectType.GRANT, "SERB Core Grant",
                  grant_number="SERB-001", amount="300000",
                  links=[(project.id, RelationshipKind.FUNDS)])
    _make(repo, ObjectType.GRANT_INSTALLMENT, "Installment 1",
          amount="100000", installment_status="released",
          links=[(grant.id, RelationshipKind.BELONGS_TO)])
    faculty.add_relationship(project.id, RelationshipKind.LEADS, actor="registrar:1")

    pub_2025 = _make(repo, ObjectType.PUBLICATION, "Ramsey Bounds",
                     publication_type="journal_article", year="2025",
                     journal="JCTA", authors=json.dumps([{"name": "Meera Krishnan"},
                                                          {"name": "Asha Verma"}]),
                     links=[(faculty.id, RelationshipKind.AUTHORED_BY),
                            (project.id, RelationshipKind.RELATED_TO)])
    pub_2026 = _make(repo, ObjectType.PUBLICATION, "Chromatic Cycles",
                     publication_type="conference_paper", year="2026",
                     conference="ICM 2026",
                     authors=json.dumps([{"name": "Meera Krishnan"}]),
                     links=[(faculty.id, RelationshipKind.AUTHORED_BY),
                            (grant.id, RelationshipKind.RELATED_TO)])

    course = _make(repo, ObjectType.COURSE, "Linear Algebra",
                   course_code="MA-201", programme="MSc Mathematics", semester="2",
                   session="2026-27", credits="4",
                   links=[(faculty.id, RelationshipKind.TAUGHT_BY)])
    student.add_relationship(course.id, RelationshipKind.ENROLLED_IN, actor="registrar:1")

    attendance = UniversalObject.create(
        object_type=ObjectType.ATTENDANCE_SESSION, title="Session 2026-01-10",
        created_by="faculty:1", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(
            session_date="2026-01-10",
            attendance_records=json.dumps({str(student.id): "present"}),
        )),
    )
    attendance.add_relationship(course.id, RelationshipKind.BELONGS_TO, actor="faculty:1")
    repo.save(attendance)
    attendance2 = UniversalObject.create(
        object_type=ObjectType.ATTENDANCE_SESSION, title="Session 2026-01-12",
        created_by="faculty:1", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(
            session_date="2026-01-12",
            attendance_records=json.dumps({str(student.id): "absent"}),
        )),
    )
    attendance2.add_relationship(course.id, RelationshipKind.BELONGS_TO, actor="faculty:1")
    repo.save(attendance2)

    assignment = _make(repo, ObjectType.ASSIGNMENT, "Problem Set 1",
                       assignment_type="assignment", max_marks="20",
                       deadline="2026-01-20", weightage="50",
                       links=[(course.id, RelationshipKind.BELONGS_TO)])
    submission = UniversalObject.create(
        object_type=ObjectType.SUBMISSION, title="Asha — PS1",
        created_by="student:1", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(marks="18", is_late="false",
                                                 submitted_at="2026-01-19")),
    )
    submission.add_relationship(assignment.id, RelationshipKind.BELONGS_TO, actor="student:1")
    submission.add_relationship(student.id, RelationshipKind.AUTHORED_BY, actor="student:1")
    repo.save(submission)

    event = _make(repo, ObjectType.EVENT, "Mathematics Day 2026",
                  event_type="mathematics_day", event_status="completed",
                  start_date="2026-12-22", department="Mathematics",
                  organizer="Dept. of Mathematics",
                  participation=json.dumps([{"role": "organizer", "contribution": "Led"}]),
                  links=[(faculty.id, RelationshipKind.RELATED_TO)])
    workshop = _make(repo, ObjectType.EVENT, "STM Workshop",
                     event_type="workshop", event_status="completed",
                     start_date="2025-11-05", department="Mathematics",
                     participation=json.dumps([{"role": "participant"}]))

    committee = _make(repo, ObjectType.COMMITTEE, "IQAC",
                      committee_type="iqac", committee_code="IQ-1",
                      members=json.dumps([{"faculty_id": str(faculty.id),
                                            "name": faculty.title, "role": "convener"}]))
    meeting = _make(repo, ObjectType.MEETING, "IQAC Meeting 1",
                    meeting_number="1", meeting_date="2026-02-10", mode="offline",
                    attendance=json.dumps([{"object_id": str(faculty.id),
                                             "name": faculty.title, "status": "present"}]),
                    links=[(committee.id, RelationshipKind.BELONGS_TO)])
    _make(repo, ObjectType.TASK, "Prepare AQAR",
          action_status="pending", assigned_name="Meera", due_date="2026-03-01",
          priority="high",
          links=[(meeting.id, RelationshipKind.BELONGS_TO)])
    _make(repo, ObjectType.TASK, "Upload minutes",
          action_status="done", assigned_name="Meera", due_date="2026-02-15",
          links=[(meeting.id, RelationshipKind.BELONGS_TO)])

    vendor = _make(repo, ObjectType.VENDOR, "Alpha Traders", gst_number="05ABCDE1234F1Z5")
    proposal = _make(repo, ObjectType.PURCHASE, "Books Purchase",
                     proposal_number="PP-001", department="Mathematics",
                     proposal_date="2026-01-15", proposal_status="approved",
                     estimated_cost="50000",
                     purchase_orders=json.dumps([{"po_number": "PO-1", "amount": "40000",
                                                   "vendor_id": str(vendor.id),
                                                   "status": "issued"}]),
                     bills=json.dumps([{"bill_number": "B-1", "amount": "38000",
                                         "gst_amount": "2000", "payment_status": "paid",
                                         "vendor_id": str(vendor.id)}]),
                     assets=json.dumps([{"asset_id": "AS-1", "category": "equipment",
                                          "item_name": "Projector", "cost": "38000",
                                          "status": "in_service"}]),
                     links=[(project.id, RelationshipKind.RELATED_TO)])

    repo.world = {  # type: ignore[attr-defined]
        "faculty": faculty, "student": student, "project": project, "grant": grant,
        "pub_2025": pub_2025, "pub_2026": pub_2026, "course": course,
        "event": event, "workshop": workshop, "committee": committee,
        "meeting": meeting, "vendor": vendor, "proposal": proposal,
    }
    return repo


def _by_key(tables, key):
    return next(t for t in tables if t.key == key)


def _kpi(view, label):
    return next(k for k in view.kpis if k.label == label).value


# ---------------------------------------------------------------------------
# PART 1 — dashboard
# ---------------------------------------------------------------------------
def test_dashboard_counts_and_budget(world):
    out = GetReportsDashboardUseCase(world).execute(GetReportsDashboardQuery())
    assert out.total_publications == 2
    assert out.total_projects == 1
    assert out.total_grants == 1
    assert out.total_students == 1
    assert out.total_classes == 1
    assert out.total_faculty == 1
    assert out.total_committees == 1
    assert out.total_events == 2
    # 500,000 approved; utilized = 120,000 (project) + 40,000 paid bill
    assert out.budget_approved == 500000.0
    assert out.budget_utilized == 160000.0
    assert out.budget_remaining == 340000.0


# ---------------------------------------------------------------------------
# PART 2 — publications
# ---------------------------------------------------------------------------
def test_publications_report_groupings(world):
    view = build_publications_report(Snapshot(world), ReportFilters())
    assert _kpi(view, "Total Publications") == "2"
    by_year = {r[0]: r[1] for r in _by_key(view.tables, "by_year").rows}
    assert by_year == {"2025": "1", "2026": "1"}
    by_journal = {r[0]: r[1] for r in _by_key(view.tables, "by_journal").rows}
    assert by_journal.get("JCTA") == "1"
    by_type = {r[0]: r[1] for r in _by_key(view.tables, "by_type").rows}
    assert by_type.get("Journal Article") == "1"
    assert by_type.get("Conference Paper") == "1"
    by_author = {r[0]: r[1] for r in _by_key(view.tables, "by_author").rows}
    assert by_author.get("Meera Krishnan") == "2"
    assert by_author.get("Asha Verma") == "1"
    by_project = {r[0]: r[1] for r in _by_key(view.tables, "by_project").rows}
    assert by_project == {"Graph Frontiers": "1"}
    by_grant = {r[0]: r[1] for r in _by_key(view.tables, "by_grant").rows}
    assert by_grant == {"SERB Core Grant": "1"}
    assert len(_by_key(view.tables, "rows").rows) == 2
    assert view.charts[0].labels == ["2025", "2026"]


def test_publications_report_filters(world):
    faculty_id = str(world.world["faculty"].id)
    view = build_publications_report(Snapshot(world), ReportFilters(year=2026))
    assert len(_by_key(view.tables, "rows").rows) == 1
    view = build_publications_report(Snapshot(world), ReportFilters(faculty_id=faculty_id))
    assert len(_by_key(view.tables, "rows").rows) == 2
    view = build_publications_report(
        Snapshot(world), ReportFilters(project_id=str(world.world["project"].id))
    )
    rows = _by_key(view.tables, "rows").rows
    assert [r[0] for r in rows] == ["Ramsey Bounds"]
    # Year-only publications follow the documented year-window rule: a
    # 2025-only publication is NOT inside 2026-01-01..2026-12-31.
    view = build_publications_report(
        Snapshot(world), ReportFilters(date_from="2026-01-01", date_to="2026-12-31")
    )
    assert [r[0] for r in _by_key(view.tables, "rows").rows] == ["Chromatic Cycles"]


# ---------------------------------------------------------------------------
# PART 3 — research
# ---------------------------------------------------------------------------
def test_research_report(world):
    view = build_research_report(world, Snapshot(world), ReportFilters())
    assert _kpi(view, "Active Projects") == "1"
    assert _kpi(view, "Completed Projects") == "0"
    budget = _by_key(view.tables, "budget_summary").rows[0]
    assert budget[1] == "₹5,00,000" and budget[2] == "₹1,00,000"
    assert budget[3] == "₹1,60,000" and budget[4] == "₹3,40,000"
    grants = _by_key(view.tables, "grant_summary").rows[0]
    assert grants[1] == "SERB-001" and grants[3] == "₹1,00,000"
    pubs = _by_key(view.tables, "project_publications").rows[0]
    assert pubs[1] == "1" and "Ramsey Bounds" in pubs[2]
    team = _by_key(view.tables, "team_summary").rows[0]
    assert "Meera Krishnan" in team[1]


# ---------------------------------------------------------------------------
# PART 4 — faculty
# ---------------------------------------------------------------------------
def test_faculty_profile(world):
    view = build_faculty_report(
        world, Snapshot(world), ReportFilters(faculty_id=str(world.world["faculty"].id))
    )
    assert "Dr. Meera Krishnan" in view.title
    assert _kpi(view, "Publications") == "2"
    assert _kpi(view, "Projects") == "1"
    assert _kpi(view, "Grants") == "1"
    assert _kpi(view, "Classes") == "1"
    assert _kpi(view, "Committees") == "1"
    assert _kpi(view, "Events") == "1"
    assert len(_by_key(view.tables, "publications").rows) == 2
    profile = {r[0]: r[1] for r in _by_key(view.tables, "profile").rows}
    assert profile.get("Department") == "Mathematics"


def test_faculty_overview_and_unknown(world):
    view = build_faculty_report(world, Snapshot(world), ReportFilters())
    assert len(_by_key(view.tables, "overview").rows) == 1
    with pytest.raises(ObjectNotFoundError):
        build_faculty_report(world, Snapshot(world), ReportFilters(faculty_id="obj:faculty:missing"))


# ---------------------------------------------------------------------------
# PART 5 — students
# ---------------------------------------------------------------------------
def test_student_profile(world):
    view = build_students_report(
        world, Snapshot(world), ReportFilters(student_id=str(world.world["student"].id))
    )
    assert _kpi(view, "Classes Enrolled") == "1"
    assert _kpi(view, "Overall Attendance") == "50%"
    assert _kpi(view, "Assignments") == "1 / 1"
    assert _kpi(view, "Marks Percentage") == "90%"
    attendance = _by_key(view.tables, "attendance_summary").rows[0]
    assert attendance[1:3] == ["2", "1"]
    marks = _by_key(view.tables, "marks_summary").rows[0]
    assert marks[1] == "18" and marks[2] == "20" and marks[3] == "90%"
    grade = _by_key(view.tables, "grade_summary").rows[0]
    assert grade[1] == "90%" and grade[2] != "—"


def test_student_overview(world):
    view = build_students_report(world, Snapshot(world), ReportFilters())
    rows = _by_key(view.tables, "overview").rows
    assert len(rows) == 1
    assert rows[0][7] == "50%"
    assert rows[0][8] == "90%"


# ---------------------------------------------------------------------------
# PART 6 — teaching
# ---------------------------------------------------------------------------
def test_teaching_report(world):
    view = build_teaching_report(world, Snapshot(world), ReportFilters())
    assert _kpi(view, "Classes") == "1"
    assert _kpi(view, "Overall Attendance") == "50%"
    assert _kpi(view, "Submissions") == "1"
    assignments = _by_key(view.tables, "assignments").rows[0]
    assert assignments[1:] == ["1", "1", "1", "90%"]
    gradebook = _by_key(view.tables, "gradebook").rows[0]
    assert gradebook[1] == "90%"
    labels = view.charts[0].labels
    assert labels == ["Linear Algebra"]


# ---------------------------------------------------------------------------
# PART 7 — finance
# ---------------------------------------------------------------------------
def test_finance_report(world):
    view = build_finance_report(world, Snapshot(world), ReportFilters())
    assert _kpi(view, "Budget Approved") == "₹5,00,000"
    assert _kpi(view, "Budget Utilized") == "₹1,60,000"
    vendor = _by_key(view.tables, "vendor_summary").rows[0]
    assert vendor[0] == "Alpha Traders" and vendor[3] == "1" and vendor[5] == "₹40,000"
    purchase = _by_key(view.tables, "purchase_summary").rows[0]
    assert purchase[0] == "PP-001" and purchase[7] == "₹40,000" and purchase[8] == "₹40,000"
    assets = _by_key(view.tables, "asset_summary").rows
    assert assets[0][0] == "AS-1" and assets[0][6] == "₹38,000"
    by_category = {r[0]: r[1] for r in _by_key(view.tables, "assets_by_category").rows}
    assert by_category == {"Equipment": "1"}


# ---------------------------------------------------------------------------
# PART 8 — events
# ---------------------------------------------------------------------------
def test_events_report(world):
    view = build_events_report(Snapshot(world), world, ReportFilters())
    assert _kpi(view, "Total Events") == "2"
    assert _kpi(view, "Organized") == "1"
    assert _kpi(view, "Attended") == "1"
    assert _kpi(view, "Workshops") == "1"
    assert _kpi(view, "Conferences") == "0"
    participation = _by_key(view.tables, "participation").rows
    assert len(participation) == 2
    assert participation[0][1] == "Organizer" or participation[1][1] == "Organizer"
    years = dict(zip(view.charts[0].labels, view.charts[0].series[0].data, strict=True))
    assert years == {"2025": 1.0, "2026": 1.0}


# ---------------------------------------------------------------------------
# PART 9 — committees
# ---------------------------------------------------------------------------
def test_committees_report(world):
    view = build_committees_report(world, Snapshot(world), ReportFilters())
    assert _kpi(view, "Meetings") == "1"
    assert _kpi(view, "Overall Attendance") == "100%"
    assert _kpi(view, "Pending Actions") == "1"
    assert _kpi(view, "Completed Actions") == "1"
    meetings = _by_key(view.tables, "meetings").rows[0]
    assert meetings[3] == "2026-02-10" and meetings[7] == "100%"
    pending = _by_key(view.tables, "pending_actions").rows
    assert [r[0] for r in pending] == ["Prepare AQAR"]
    completed = _by_key(view.tables, "completed_actions").rows
    assert [r[0] for r in completed] == ["Upload minutes"]


# ---------------------------------------------------------------------------
# PART 10 — analytics
# ---------------------------------------------------------------------------
def test_analytics_report(world):
    view = build_analytics_report(Snapshot(world), world, ReportFilters())
    keys = [chart.key for chart in view.charts]
    assert keys == ["publication_trend", "event_trend", "budget_trend",
                    "teaching_load", "attendance_trend"]
    trend = {c.key: c for c in view.charts}["publication_trend"]
    assert trend.labels == ["2024", "2025", "2026"]
    assert trend.series[0].data == [0.0, 1.0, 1.0]
    attendance = {c.key: c for c in view.charts}["attendance_trend"]
    assert attendance.labels == ["2026-01"]
    assert attendance.series[0].data == [50.0]
    load = {c.key: c for c in view.charts}["teaching_load"]
    assert load.labels == ["Dr. Meera Krishnan"]


# ---------------------------------------------------------------------------
# PART 12 — filters validation
# ---------------------------------------------------------------------------
def test_filter_validation():
    with pytest.raises(ValidationError):
        assert_valid_filters(ReportFilters(date_from="not-a-date"), "publications")
    with pytest.raises(ValidationError):
        assert_valid_filters(ReportFilters(year=1700), "publications")
    with pytest.raises(ValidationError):
        assert_valid_filters(
            ReportFilters(date_from="2026-02-01", date_to="2026-01-01"), "publications"
        )
    # Filters a kind does not honour are dropped (analytics ignores pickers).
    cleaned = assert_valid_filters(
        ReportFilters(committee_id="obj:committee:x"), "analytics"
    )
    assert cleaned.committee_id is None
    # …and students snapshot-picker is dropped from the publications report.
    cleaned = assert_valid_filters(
        ReportFilters(student_id="obj:student:x"), "publications"
    )
    assert cleaned.student_id is None


# ---------------------------------------------------------------------------
# PART 11 — exporters
# ---------------------------------------------------------------------------
def test_exporters(world):
    import csv

    text = ExportReportUseCase(world).execute(
        ExportReportQuery(kind="publications", format="csv", filters=ReportFilters())
    )
    assert text.media_type.startswith("text/csv")
    rows = list(csv.reader(io.StringIO(text.content.decode("utf-8-sig"))))
    header = next(r for r in rows if r and r[0] == "Publications by Year")
    idx = rows.index(header)
    assert rows[idx + 1] == ["Year", "Publications"]

    xlsx = ExportReportUseCase(world).execute(
        ExportReportQuery(kind="publications", format="xlsx", filters=ReportFilters())
    )
    assert xlsx.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(xlsx.content)) as archive:
        names = archive.namelist()
        assert "xl/workbook.xml" in names
        workbook = archive.read("xl/workbook.xml").decode()
        assert "Summary" in workbook
        assert any(name.startswith("xl/worksheets/sheet") for name in names)

    pdf = ExportReportUseCase(world).execute(
        ExportReportQuery(kind="publications", format="pdf", filters=ReportFilters())
    )
    assert pdf.content.startswith(b"%PDF-1.4")
    assert b"Publications" in pdf.content
    assert pdf.filename.endswith(".pdf")
    assert "publications" in pdf.filename

    with pytest.raises(ValidationError):
        ExportReportUseCase(world).execute(
            ExportReportQuery(kind="publications", format="doc", filters=ReportFilters())
        )
    with pytest.raises(ValidationError):
        ExportReportUseCase(world).execute(
            ExportReportQuery(kind="nope", format="csv", filters=ReportFilters())
        )


def test_export_matches_workspace_view(world):
    """The export is the same computed view the workspace renders (PART 11
    reuse — no duplicate logic)."""
    result = ExportReportUseCase(world).execute(
        ExportReportQuery(kind="publications", format="csv",
                          filters=ReportFilters(year=2026))
    )
    text = result.content.decode("utf-8-sig")
    assert "Chromatic Cycles" in text
    assert "Ramsey Bounds" not in text
    assert "year=2026" in text
