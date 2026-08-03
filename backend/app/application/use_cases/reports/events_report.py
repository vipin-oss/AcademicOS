"""Use case: Events report (PART 8).

Events organized / attended / participation / certificates / workshops /
conferences lenses over the frozen Events module's data — the dashboard card
predicates (organized = participation role in ORGANIZER_ROLES, attended =
ATTENDEE_ROLES, certificates = participation rows carrying a certificate
document) reused one-to-one so the report always agrees with the Events
dashboard. Computed read — nothing stored.
"""
from __future__ import annotations

from app.application.dtos.events import (
    ATTENDEE_ROLES,
    KEY_DEPARTMENT,
    KEY_END_DATE,
    KEY_EVENT_TYPE,
    KEY_ORGANIZER,
    KEY_PARTICIPATION,
    KEY_START_DATE,
    ORGANIZER_ROLES,
    parse_json_object_list,
)
from app.application.dtos.reports import ReportView
from app.application.queries.get_events_report import GetEventsReportQuery
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    count_by,
    department_matches,
    fmt_int,
    href_for,
    in_filter_window,
    kpi,
    meta_of,
    now_iso,
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

KIND = "events"
REPORT_TITLE = "Events Report"


def _filtered(snapshot: Snapshot, filters) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for event in snapshot["events"]:
        meta = meta_of(event)
        if filters.event_id and str(event.id) != filters.event_id:
            continue
        if not in_filter_window(meta.get(KEY_START_DATE), filters):
            continue
        if not department_matches(meta.get(KEY_DEPARTMENT), filters.department):
            continue
        if filters.faculty_id and not any(
            str(rel.target) == filters.faculty_id for rel in event.relationships
        ):
            continue
        out.append(event)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def _roles_of(meta: dict[str, str]) -> set[str]:
    return {
        str(row.get("role") or "")
        for row in parse_json_object_list(meta.get(KEY_PARTICIPATION))
        if isinstance(row, dict) and row.get("role")
    }


def _event_row(snapshot: Snapshot, event: UniversalObject, meta: dict[str, str]) -> list[str]:
    return [
        event.title,
        title_case(meta.get(KEY_EVENT_TYPE)),
        (meta.get(KEY_START_DATE) or "—"),
        (meta.get(KEY_END_DATE) or "—"),
        ", ".join(sorted(title_case(r) for r in _roles_of(meta))) or "—",
        (meta.get(KEY_ORGANIZER) or "—"),
    ]


def build_events_report(snapshot: Snapshot, repository: ObjectRepository, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)
    events = _filtered(snapshot, filters)

    organized: list[UniversalObject] = []
    attended: list[UniversalObject] = []
    participation_rows: list[list[str]] = []
    participation_hrefs: list[list[str | None]] = []
    certificate_rows: list[list[str]] = []
    certificate_hrefs: list[list[str | None]] = []
    workshops: list[UniversalObject] = []
    conferences: list[UniversalObject] = []

    for event in events:
        meta = meta_of(event)
        roles = _roles_of(meta)
        if roles & set(ORGANIZER_ROLES):
            organized.append(event)
        if roles & set(ATTENDEE_ROLES):
            attended.append(event)
        if (meta.get(KEY_EVENT_TYPE) or "") == "workshop":
            workshops.append(event)
        if (meta.get(KEY_EVENT_TYPE) or "") == "conference":
            conferences.append(event)
        for row in parse_json_object_list(meta.get(KEY_PARTICIPATION)):
            if not isinstance(row, dict) or not row.get("role"):
                continue
            participation_rows.append([
                event.title,
                title_case(str(row.get("role"))),
                str(row.get("contribution") or "—"),
                str(row.get("remarks") or "—"),
            ])
            participation_hrefs.append([href_for(event), None, None, None])
            document_id = str(row.get("certificate_document_id") or "")
            if document_id:
                document = snapshot.get(document_id)
                certificate_rows.append([
                    event.title,
                    title_case(str(row.get("role"))),
                    document.title if document is not None else document_id,
                ])
                certificate_hrefs.append([
                    href_for(event), None,
                    href_for(document) if document is not None else None,
                ])

    def _rows(bucket: list[UniversalObject]) -> tuple[list[list[str]], list[list[str | None]]]:
        return (
            [_event_row(snapshot, e, meta_of(e)) for e in bucket],
            [[href_for(e), None, None, None, None, None] for e in bucket],
        )

    organized_rows, organized_hrefs = _rows(organized)
    attended_rows, attended_hrefs = _rows(attended)
    workshop_rows, workshop_hrefs = _rows(workshops)
    conference_rows, conference_hrefs = _rows(conferences)

    year_buckets = count_by(
        [str(y) if (y := year_of(meta_of(e).get(KEY_START_DATE))) else None for e in events]
    )
    years = sorted(year_buckets.items())
    types = sorted_buckets(count_by([meta_of(e).get(KEY_EVENT_TYPE) for e in events]))

    tables = [
        table("events_organized", "Events Organized",
              ("Title", "Type", "Start", "End", "My Roles", "Organizer"),
              organized_rows, organized_hrefs),
        table("events_attended", "Events Attended",
              ("Title", "Type", "Start", "End", "My Roles", "Organizer"),
              attended_rows, attended_hrefs),
        table("participation", "Participation",
              ("Event", "Role", "Contribution", "Remarks"),
              participation_rows, participation_hrefs),
        table("certificates", "Certificates",
              ("Event", "Role", "Certificate Document"),
              certificate_rows, certificate_hrefs),
        table("workshops", "Workshops",
              ("Title", "Type", "Start", "End", "My Roles", "Organizer"),
              workshop_rows, workshop_hrefs),
        table("conferences", "Conferences",
              ("Title", "Type", "Start", "End", "My Roles", "Organizer"),
              conference_rows, conference_hrefs),
    ]
    charts = [
        bar_chart("per_year", "Events per Year",
                  [label for label, _ in years], [float(n) for _, n in years],
                  name="Events"),
        bar_chart("per_type", "Events by Type",
                  [title_case(t) for t, _ in types], [float(n) for _, n in types],
                  name="Events"),
    ]
    kpis = [
        kpi("Total Events", fmt_int(len(events))),
        kpi("Organized", fmt_int(len(organized))),
        kpi("Attended", fmt_int(len(attended))),
        kpi("Certificates", fmt_int(len(certificate_rows))),
        kpi("Workshops", fmt_int(len(workshops))),
        kpi("Conferences", fmt_int(len(conferences))),
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


class GetEventsReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetEventsReportQuery) -> ReportView:
        return build_events_report(
            Snapshot(self._repository), self._repository, query.filters
        )
