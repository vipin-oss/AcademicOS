"""Use case: Publications report (PART 2).

Group-by lenses over the frozen Publications module's data: year, journal,
conference, publication type, author, project, grant — each as a count table,
plus the filtered master table and per-year / per-type charts. Computed read:
the Publication Objects are scanned once and bucketed; nothing is stored.

PART 12 filters honoured (see ``FILTER_KEYS_BY_KIND``): year, date range,
faculty (AUTHORED_BY edge — the faculty module's link), project, grant (any
relationship edge — the generic relationship-lens precedent). A publication
carrying only a year (no full date) matches a date range when its year lies
inside the range (documented; month precision needs KEY_DATE present).
"""
from __future__ import annotations

from app.application.dtos.publication import (
    KEY_AUTHORS,
    KEY_CONFERENCE,
    KEY_DATE,
    KEY_JOURNAL,
    KEY_PUBLICATION_TYPE,
    KEY_YEAR,
)
from app.application.dtos.reports import ReportView
from app.application.queries.get_publications_report import GetPublicationsReportQuery
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    count_by,
    fmt_int,
    href_for,
    in_filter_window,
    kpi,
    linked_ids,
    meta_of,
    now_iso,
    parse_json_list,
    sorted_buckets,
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

KIND = "publications"
REPORT_TITLE = "Publications Report"


def _publication_window(meta: dict[str, str], filters) -> bool:
    """PART 12 window for publications (year-aware; see module docstring)."""
    if meta.get(KEY_DATE):
        return in_filter_window(meta[KEY_DATE], filters)
    year = year_of(meta.get(KEY_YEAR))
    if filters.year is not None and year != filters.year:
        return False
    if filters.date_from or filters.date_to:
        if year is None:
            return False
        from_year = year_of(filters.date_from)
        to_year = year_of(filters.date_to)
        if from_year is not None and year < from_year:
            return False
        if to_year is not None and year > to_year:
            return False
    return True


def _filtered(snapshot: Snapshot, filters) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for pub in snapshot["publications"]:
        meta = meta_of(pub)
        if not _publication_window(meta, filters):
            continue
        if filters.faculty_id and not any(
            rel.kind is RelationshipKind.AUTHORED_BY and str(rel.target) == filters.faculty_id
            for rel in pub.relationships
        ):
            continue
        ids = linked_ids(pub)
        if filters.project_id and filters.project_id not in ids:
            continue
        if filters.grant_id and filters.grant_id not in ids:
            continue
        out.append(pub)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def _authors_of(meta: dict[str, str]) -> list[str]:
    names: list[str] = []
    for row in parse_json_list(meta.get(KEY_AUTHORS)):
        if isinstance(row, dict):
            name = str(row.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _linked_buckets(
    snapshot: Snapshot, pubs: list[UniversalObject], bucket: str
) -> list[tuple[str, UniversalObject | None, int]]:
    """Publications grouped by each linked object of a type (a publication
    counts once per linked target — the group-by convention)."""
    known = {str(obj.id): obj for obj in snapshot[bucket]}
    counts: dict[str, int] = {}
    for pub in pubs:
        for target in linked_ids(pub) & set(known):
            counts[target] = counts.get(target, 0) + 1
    rows = [(known[t].title, known[t], n) for t, n in counts.items()]
    rows.sort(key=lambda row: (-row[2], row[0].casefold(), str(row[1].id)))
    return rows


def build_publications_report(snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    pubs = _filtered(snapshot, filters)
    metas = [meta_of(pub) for pub in pubs]

    years = sorted_buckets(
        count_by(
            [str(y) if (y := year_of(m.get(KEY_YEAR))) is not None else None for m in metas]
        ),
        numeric_keys=True,
    )
    journals = sorted_buckets(count_by([m.get(KEY_JOURNAL) for m in metas]))
    conferences = sorted_buckets(count_by([m.get(KEY_CONFERENCE) for m in metas]))
    types = sorted_buckets(count_by([m.get(KEY_PUBLICATION_TYPE) for m in metas]))
    author_counts: dict[str, int] = {}
    for m in metas:
        for name in _authors_of(m):
            author_counts[name] = author_counts.get(name, 0) + 1
    authors = sorted_buckets(author_counts)
    project_rows = _linked_buckets(snapshot, pubs, "projects")
    grant_rows = _linked_buckets(snapshot, pubs, "grants")
    project_ids = {s for _, obj, _ in project_rows if obj is not None for s in [str(obj.id)]}

    master_rows: list[list[str]] = []
    master_hrefs: list[list[str | None]] = []
    for pub, meta in zip(pubs, metas, strict=True):
        master_rows.append([
            pub.title,
            title_case(meta.get(KEY_PUBLICATION_TYPE)),
            str(y) if (y := year_of(meta.get(KEY_YEAR) or meta.get(KEY_DATE))) is not None else "—",
            (meta.get(KEY_JOURNAL) or "").strip() or "—",
            (meta.get(KEY_CONFERENCE) or "").strip() or "—",
            ", ".join(_authors_of(meta)) or "—",
        ])
        master_hrefs.append([href_for(pub), None, None, None, None, None])

    tables = [
        table("by_year", "Publications by Year", ("Year", "Publications"),
              [[label, fmt_int(n)] for label, n in years]),
        table("by_journal", "Publications by Journal", ("Journal", "Publications"),
              [[label, fmt_int(n)] for label, n in journals]),
        table("by_conference", "Publications by Conference", ("Conference", "Publications"),
              [[label, fmt_int(n)] for label, n in conferences]),
        table("by_type", "Publications by Type", ("Publication Type", "Publications"),
              [[title_case(label), fmt_int(n)] for label, n in types]),
        table("by_author", "Publications by Author", ("Author", "Publications"),
              [[label, fmt_int(n)] for label, n in authors]),
        table("by_project", "Publications by Project", ("Project", "Publications"),
              [[label, fmt_int(n)] for label, _, n in project_rows],
              [[href_for(obj) if obj is not None else None, None] for _, obj, _ in project_rows]),
        table("by_grant", "Publications by Grant", ("Grant", "Publications"),
              [[label, fmt_int(n)] for label, _, n in grant_rows],
              [[href_for(obj) if obj is not None else None, None] for _, obj, _ in grant_rows]),
        table("rows", "Publications (filtered)",
              ("Title", "Type", "Year", "Journal", "Conference", "Authors"),
              master_rows, master_hrefs),
    ]

    charts = [
        bar_chart("per_year", "Publications per Year",
                  [label for label, _ in years], [float(n) for _, n in years],
                  name="Publications"),
        bar_chart("per_type", "Publications by Type",
                  [title_case(label) for label, _ in types], [float(n) for _, n in types],
                  name="Publications"),
    ]

    linked_to_projects = sum(
        1 for pub in pubs if linked_ids(pub) & project_ids
    )
    kpis = [
        kpi("Total Publications", fmt_int(len(pubs))),
        kpi("In Journals", fmt_int(sum(1 for m in metas if (m.get(KEY_JOURNAL) or "").strip()))),
        kpi("In Conferences", fmt_int(sum(1 for m in metas if (m.get(KEY_CONFERENCE) or "").strip()))),
        kpi("Distinct Authors", fmt_int(len(author_counts))),
        kpi("Linked to Projects", fmt_int(linked_to_projects)),
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


class GetPublicationsReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetPublicationsReportQuery) -> ReportView:
        return build_publications_report(Snapshot(self._repository), query.filters)
