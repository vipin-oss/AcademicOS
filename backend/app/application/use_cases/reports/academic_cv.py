"""Academic CV Generation — consolidated export pulling from ALL modules.

Generates a professor's complete academic CV from confirmed records:
- Profile / Summary
- Publications (journal papers, conference papers, book chapters)
- Research Projects & Grants
- Events & Conferences (attended, organized, presented)
- Teaching (courses, student supervision)
- Committee Memberships

Uses the same ReportView + exporter infrastructure as the per-module reports.
"""
from __future__ import annotations

import json
from datetime import date

from app.application.dtos.reports import (
    ReportFilters,
    ReportKpi,
    ReportTable,
    ReportView,
    fmt_int,
)
from app.application.use_cases.reports.helpers import (
    Snapshot,
    meta_of,
    now_iso,
    title_case,
    year_of,
    iso_date,
    in_filter_window,
    parse_json_list,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _format_authors(raw: str | None) -> str:
    """Parse author metadata and return formatted string.
    
    Handles:
    - JSON array of objects: [{"name": "Dr. Alice"}, {"name": "Prof. Bob"}]
    - JSON array of strings: ["Dr. Alice", "Prof. Bob"]
    - Plain string: "Dr. Alice, Prof. Bob"
    - Legacy/malformed: return as-is
    """
    if not raw:
        return "—"
    
    raw = str(raw).strip()
    if not raw:
        return "—"
    
    # Try JSON parsing
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                names = []
                for item in parsed:
                    if isinstance(item, dict):
                        name = item.get("name", "").strip()
                        if name:
                            names.append(name)
                    elif isinstance(item, str):
                        names.append(item.strip())
                if names:
                    return ", ".join(names)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Already a plain string
    return raw


def _sort_by_date(items: list[UniversalObject], date_key: str, reverse: bool = True) -> list[UniversalObject]:
    """Sort objects by a date metadata field (newest first by default)."""
    def sort_key(obj: UniversalObject):
        m = meta_of(obj)
        d = iso_date(m.get(date_key)) or iso_date(m.get("start_date")) or iso_date(m.get("created_at"))
        return d.isoformat() if d else "0000"
    return sorted(items, key=sort_key, reverse=reverse)


def _deduplicate(items: list[UniversalObject]) -> list[UniversalObject]:
    """Remove duplicate records based on title + date + type.
    
    Keeps the first occurrence (newest due to sorting).
    """
    seen: set[tuple[str, str, str]] = set()
    result = []
    for obj in items:
        m = meta_of(obj)
        # Create a dedup key from title + date + type
        title_key = obj.title.strip().lower()[:100]
        date_key = (m.get("start_date") or m.get("publication_year") or m.get("created_at") or "")[:10]
        type_key = m.get("event_type") or m.get("publication_type") or ""
        dedup_key = (title_key, date_key, type_key)
        
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append(obj)
    return result


def _build_profile_section(snapshot: Snapshot) -> list[ReportKpi]:
    """Build profile summary from faculty records."""
    faculty = snapshot["faculty"]
    if not faculty:
        return []

    prof = faculty[0]  # Primary faculty record
    m = meta_of(prof)

    kpis = [
        ReportKpi(label="Name", value=prof.title),
    ]
    
    designation = m.get("designation", "").strip()
    if designation:
        kpis.append(ReportKpi(label="Designation", value=designation))
    
    department = m.get("department", "").strip()
    if department:
        kpis.append(ReportKpi(label="Department", value=department))
    
    institution = m.get("institution", "").strip()
    if institution:
        kpis.append(ReportKpi(label="Institution", value=institution))
    
    email = m.get("email", "").strip()
    if email:
        kpis.append(ReportKpi(label="Email", value=email))
    
    orcid = m.get("orcid", "").strip()
    if orcid:
        kpis.append(ReportKpi(label="ORCID", value=orcid))

    return kpis


def _build_publications_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List all publications, newest first, filtered by year if specified."""
    pubs = snapshot["publications"]
    if not pubs:
        return None

    # Apply year filter
    filtered_pubs = []
    for pub in pubs:
        m = meta_of(pub)
        pub_year = m.get("publication_year")
        if in_filter_window(pub_year, filters):
            filtered_pubs.append(pub)
    
    if not filtered_pubs:
        return None

    sorted_pubs = _sort_by_date(filtered_pubs, "publication_year")
    sorted_pubs = _deduplicate(sorted_pubs)
    
    rows = []
    hrefs = []
    for pub in sorted_pubs:
        m = meta_of(pub)
        year = m.get("publication_year", "—")
        authors = _format_authors(m.get("authors"))
        journal = m.get("journal_name", "")
        doi = m.get("doi", "")
        venue = journal or doi or "—"
        rows.append([pub.title, authors, str(year), venue])
        hrefs.append([f"/publications/{pub.id}", None, None, None])

    return ReportTable(
        key="publications",
        title="Publications",
        columns=("Title", "Authors", "Year", "Journal / DOI"),
        rows=rows,
        hrefs=hrefs,
    )


def _build_research_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List research projects and grants, filtered by year if specified."""
    projects = snapshot["projects"]
    grants = snapshot["grants"]

    all_items = []
    for proj in projects:
        m = meta_of(proj)
        if not in_filter_window(m.get("start_date"), filters):
            continue
        all_items.append([
            proj.title,
            "Project",
            m.get("funding_agency", "—"),
            m.get("sanctioned_amount", "—"),
            m.get("project_status", "—"),
            f"/research/projects/{proj.id}",
        ])
    for grant in grants:
        m = meta_of(grant)
        if not in_filter_window(m.get("start_date"), filters):
            continue
        all_items.append([
            grant.title,
            "Grant",
            m.get("funding_agency", "—"),
            m.get("sanctioned_amount", "—"),
            m.get("project_status", "—"),
            f"/research/grants/{grant.id}",
        ])

    if not all_items:
        return None

    # Deduplicate by title
    seen_titles: set[str] = set()
    deduped = []
    for item in all_items:
        title_key = item[0].strip().lower()[:100]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(item)

    rows = [[r[0], r[1], r[2], r[3], r[4]] for r in deduped]
    hrefs = [[r[5], None, None, None, None] for r in deduped]

    return ReportTable(
        key="research",
        title="Research Projects & Grants",
        columns=("Title", "Type", "Funding Agency", "Amount", "Status"),
        rows=rows,
        hrefs=hrefs,
    )


def _build_events_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List events/conferences attended or organized, filtered by year if specified."""
    events = snapshot["events"]
    if not events:
        return None

    # Apply year filter
    filtered_events = []
    for evt in events:
        m = meta_of(evt)
        if in_filter_window(m.get("start_date"), filters):
            filtered_events.append(evt)
    
    if not filtered_events:
        return None

    sorted_events = _sort_by_date(filtered_events, "start_date")
    sorted_events = _deduplicate(sorted_events)
    
    rows = []
    hrefs = []
    for evt in sorted_events:
        m = meta_of(evt)
        role = m.get("participation_type", m.get("role", "—"))
        venue = m.get("venue", m.get("city", "—"))
        start = m.get("start_date", "—")
        end = m.get("end_date", "")
        date_str = f"{start}" + (f" to {end}" if end else "")
        rows.append([evt.title, title_case(m.get("event_type", "")), role, venue, date_str])
        hrefs.append([f"/events/{evt.id}", None, None, None, None])

    return ReportTable(
        key="events",
        title="Conferences & Events",
        columns=("Event", "Type", "Role", "Venue", "Date"),
        rows=rows,
        hrefs=hrefs,
    )


def _build_teaching_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List teaching courses, filtered by year if specified."""
    classes = snapshot["classes"]
    if not classes:
        return None

    # Apply year filter
    filtered_classes = []
    for cls in classes:
        m = meta_of(cls)
        if in_filter_window(m.get("academic_year"), filters):
            filtered_classes.append(cls)
    
    if not filtered_classes:
        return None

    rows = []
    hrefs = []
    for cls in filtered_classes:
        m = meta_of(cls)
        rows.append([
            cls.title,
            m.get("course_code", "—"),
            m.get("semester", "—"),
            m.get("academic_year", "—"),
            m.get("credits", "—"),
        ])
        hrefs.append([f"/teaching/classes/{cls.id}", None, None, None, None])

    return ReportTable(
        key="teaching",
        title="Teaching",
        columns=("Course", "Code", "Semester", "Year", "Credits"),
        rows=rows,
        hrefs=hrefs,
    )


def _build_committees_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List committee memberships, filtered by year if specified."""
    committees = snapshot["committees"]
    if not committees:
        return None

    # Apply year filter
    filtered = []
    for com in committees:
        m = meta_of(com)
        if in_filter_window(m.get("start_date"), filters):
            filtered.append(com)
    
    if not filtered:
        return None

    rows = []
    hrefs = []
    for com in filtered:
        m = meta_of(com)
        rows.append([
            com.title,
            m.get("committee_role", m.get("role", "—")),
            m.get("committee_type", "—"),
            m.get("start_date", "—"),
            m.get("end_date", "Present"),
        ])
        hrefs.append([f"/committees/{com.id}", None, None, None, None])

    return ReportTable(
        key="committees",
        title="Committee Memberships",
        columns=("Committee", "Role", "Type", "From", "To"),
        rows=rows,
        hrefs=hrefs,
    )


def _build_students_section(snapshot: Snapshot, filters: ReportFilters) -> ReportTable | None:
    """List student supervision, filtered by year if specified."""
    students = snapshot["students"]
    if not students:
        return None

    # Apply year filter
    filtered = []
    for stu in students:
        m = meta_of(stu)
        if in_filter_window(m.get("start_date") or m.get("admission_date"), filters):
            filtered.append(stu)
    
    if not filtered:
        return None

    rows = []
    hrefs = []
    for stu in filtered:
        m = meta_of(stu)
        rows.append([
            stu.title,
            m.get("degree", m.get("student_type", "—")),
            m.get("research_topic", m.get("topic", "—")),
            m.get("phd_status", m.get("status", "—")),
        ])
        hrefs.append([f"/students/{stu.id}", None, None, None])

    return ReportTable(
        key="students",
        title="Student Supervision",
        columns=("Student", "Degree", "Topic", "Status"),
        rows=rows,
        hrefs=hrefs,
    )


def build_academic_cv(
    repository: ObjectRepository,
    filters: ReportFilters | None = None,
    user_id: str | None = None,
) -> ReportView:
    """Build a consolidated Academic CV from all modules.
    
    Args:
        repository: The object repository
        filters: Optional year/date filters
        user_id: The authenticated user's ID for ACL enforcement
    """
    # Use user-scoped snapshot for ACL enforcement
    snapshot = Snapshot(repository, user_id=user_id)
    filters = filters or ReportFilters()

    # Profile
    profile_kpis = _build_profile_section(snapshot)

    # Count totals for summary (using filtered data)
    total_pubs = len([p for p in snapshot["publications"] 
                      if in_filter_window(meta_of(p).get("publication_year"), filters)])
    total_events = len([e for e in snapshot["events"] 
                        if in_filter_window(meta_of(e).get("start_date"), filters)])
    total_projects = len([p for p in snapshot["projects"] 
                          if in_filter_window(meta_of(p).get("start_date"), filters)])
    total_grants = len([g for g in snapshot["grants"] 
                        if in_filter_window(meta_of(g).get("start_date"), filters)])
    total_students = len(snapshot["students"])
    total_classes = len([c for c in snapshot["classes"] 
                         if in_filter_window(meta_of(c).get("academic_year"), filters)])
    total_committees = len(snapshot["committees"])

    summary_kpis = [
        ReportKpi(label="Publications", value=fmt_int(total_pubs)),
        ReportKpi(label="Conferences & Events", value=fmt_int(total_events)),
        ReportKpi(label="Research Projects", value=fmt_int(total_projects + total_grants)),
        ReportKpi(label="Students Supervised", value=fmt_int(total_students)),
        ReportKpi(label="Courses Taught", value=fmt_int(total_classes)),
        ReportKpi(label="Committees", value=fmt_int(total_committees)),
    ]

    # Build sections
    tables: list[ReportTable] = []

    pub_table = _build_publications_section(snapshot, filters)
    if pub_table:
        tables.append(pub_table)

    research_table = _build_research_section(snapshot, filters)
    if research_table:
        tables.append(research_table)

    events_table = _build_events_section(snapshot, filters)
    if events_table:
        tables.append(events_table)

    teaching_table = _build_teaching_section(snapshot, filters)
    if teaching_table:
        tables.append(teaching_table)

    students_table = _build_students_section(snapshot, filters)
    if students_table:
        tables.append(students_table)

    committees_table = _build_committees_section(snapshot, filters)
    if committees_table:
        tables.append(committees_table)

    # Build applied filters string
    applied = {}
    if filters.year is not None:
        applied["year"] = str(filters.year)
    if filters.date_from:
        applied["date_from"] = filters.date_from
    if filters.date_to:
        applied["date_to"] = filters.date_to

    return ReportView(
        kind="academic_cv",
        title="Academic Curriculum Vitae",
        generated_at=now_iso(),
        applied_filters=applied,
        kpis=[*profile_kpis, *summary_kpis],
        tables=tables,
    )
