"""Shared helpers for the Reports & Analytics use cases.

Everything here is a *computed read* over the frozen modules' data — the
events/finance dashboard precedent taken module-wide: one ``Snapshot`` scans
the repository once per object type per request, and the PART 2..10 builders
compose those objects (metadata + relationships) with the frozen modules' own
helpers where they already answer the question (budgets, gradebook, event
dashboard, …). NO data is persisted by this module.
"""
from __future__ import annotations

from datetime import date, datetime

from app.application.dtos.reports import (
    CHART_BAR,
    CHART_LINE,
    ReportChart,
    ReportChartSeries,
    ReportFilters,
    ReportKpi,
    ReportTable,
    fmt_int,  # noqa: F401  (re-export)
    fmt_money,  # noqa: F401  (re-export)
    fmt_number,  # noqa: F401  (re-export)
    fmt_pct,  # noqa: F401  (re-export)
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType

# ---------------------------------------------------------------------------
# Snapshot — one scan per object type per request
# ---------------------------------------------------------------------------
SNAPSHOT_TYPES: dict[str, ObjectType] = {
    "publications": ObjectType.PUBLICATION,
    "projects": ObjectType.RESEARCH_PROJECT,
    "grants": ObjectType.GRANT,
    "installments": ObjectType.GRANT_INSTALLMENT,
    "students": ObjectType.STUDENT,
    "classes": ObjectType.COURSE,
    "assignments": ObjectType.ASSIGNMENT,
    "submissions": ObjectType.SUBMISSION,
    "attendance_sessions": ObjectType.ATTENDANCE_SESSION,
    "faculty": ObjectType.FACULTY,
    "committees": ObjectType.COMMITTEE,
    "meetings": ObjectType.MEETING,
    "tasks": ObjectType.TASK,
    "events": ObjectType.EVENT,
    "proposals": ObjectType.PURCHASE,
    "vendors": ObjectType.VENDOR,
    "documents": ObjectType.DOCUMENT,
    "agencies": ObjectType.FUNDING_AGENCY,
}


class Snapshot:
    """Per-request read model: lazily caches ``find_by_type`` results."""

    def __init__(self, repository: ObjectRepository, user_id: str | None = None) -> None:
        self._repository = repository
        self._user_id = user_id
        self._cache: dict[str, list[UniversalObject]] = {}
        self._by_id: dict[str, UniversalObject] | None = None

    def __getitem__(self, key: str) -> list[UniversalObject]:
        if key not in self._cache:
            if self._user_id:
                self._cache[key] = list(self._repository.find_by_type_for_user(SNAPSHOT_TYPES[key], self._user_id))
            else:
                self._cache[key] = list(self._repository.find_by_type(SNAPSHOT_TYPES[key]))
        return self._cache[key]

    def by_id(self) -> dict[str, UniversalObject]:
        if self._by_id is None:
            merged: dict[str, UniversalObject] = {}
            for key in SNAPSHOT_TYPES:
                for obj in self[key]:
                    merged[str(obj.id)] = obj
            self._by_id = merged
        return self._by_id

    def get(self, object_id: str | None) -> UniversalObject | None:
        return self.by_id().get(object_id or "")


# ---------------------------------------------------------------------------
# Metadata + date primitives
# ---------------------------------------------------------------------------
def meta_of(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def parse_amount(raw) -> float | None:
    """``"12345.50"`` -> 12345.5 (metadata carries decimal strings)."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_json_list(raw: str | None) -> list:
    """Metadata JSON list (the publication ``parse_json_list`` convention)."""
    import json

    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def parse_json_dict(raw: str | None) -> dict:
    import json

    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def iso_date(raw: str | None) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` (or datetime prefix) from metadata."""
    if not raw:
        return None
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def year_of(raw: str | None) -> int | None:
    parsed = iso_date(raw)
    if parsed is not None:
        return parsed.year
    if raw:
        text = str(raw).strip()
        if text.isdigit() and len(text) == 4:
            return int(text)
    return None


def in_filter_window(raw: str | None, filters: ReportFilters) -> bool:
    """PART 12: year + date-range window (inclusive) against one date field."""
    parsed = iso_date(raw)
    year = year_of(raw)
    if filters.year is not None and year != filters.year:
        return False
    if filters.date_from and (parsed is None or parsed.isoformat() < filters.date_from):
        return False
    if filters.date_to and (parsed is None or parsed.isoformat() > filters.date_to):
        return False
    return True


def department_matches(value: str | None, department: str | None) -> bool:
    if not department:
        return True
    return (value or "").strip().casefold() == department.strip().casefold()


# ---------------------------------------------------------------------------
# Relationship primitives (the publication ``linked_target_ids`` convention)
# ---------------------------------------------------------------------------
def linked_ids(obj: UniversalObject) -> set[str]:
    return {str(rel.target) for rel in obj.relationships}


def has_edge_to(obj: UniversalObject, target_id: str | None) -> bool:
    if not target_id:
        return True
    return target_id in linked_ids(obj)


def linked_from(snapshot: Snapshot, bucket: str, target_id: str) -> list[UniversalObject]:
    """Objects in ``bucket`` carrying an edge to ``target_id`` (any kind —
    the relationship-lens precedent: lenses are kind-agnostic at read time)."""
    return sorted(
        (obj for obj in snapshot[bucket] if target_id in linked_ids(obj)),
        key=lambda obj: (obj.title.casefold(), str(obj.id)),
    )


# ---------------------------------------------------------------------------
# Hrefs — frontend workspace routes, one per module (export ignores these)
# ---------------------------------------------------------------------------
def href_for(obj: UniversalObject) -> str:
    base = {
        ObjectType.PUBLICATION: "/publications",
        ObjectType.RESEARCH_PROJECT: "/research/projects",
        ObjectType.GRANT: "/research/grants",
        ObjectType.STUDENT: "/students",
        ObjectType.COURSE: "/teaching/classes",
        ObjectType.ASSIGNMENT: "/teaching/assignments",
        ObjectType.FACULTY: "/faculty",
        ObjectType.COMMITTEE: "/committees",
        ObjectType.MEETING: "/committees/meetings",
        ObjectType.EVENT: "/events",
        ObjectType.PURCHASE: "/finance",
        ObjectType.DOCUMENT: "/documents",
    }.get(obj.object_type)
    if base is None:
        return ""
    return f"{base}/{obj.id}"


# ---------------------------------------------------------------------------
# Report builders — small typed conveniences
# ---------------------------------------------------------------------------
def kpi(label: str, value) -> ReportKpi:
    return ReportKpi(label=label, value=str(value))


def table(
    key: str,
    title: str,
    columns: tuple[str, ...] | list[str],
    rows: list[list[str]],
    hrefs: list[list[str | None]] | None = None,
) -> ReportTable:
    return ReportTable(key=key, title=title, columns=tuple(columns), rows=rows, hrefs=hrefs)


def bar_chart(key: str, title: str, labels: list[str], data: list[float], name: str = "Count") -> ReportChart:
    return ReportChart(key=key, title=title, kind=CHART_BAR, labels=labels,
                       series=[ReportChartSeries(name=name, data=data)])


def line_chart(key: str, title: str, labels: list[str], data: list[float], name: str = "Count") -> ReportChart:
    return ReportChart(key=key, title=title, kind=CHART_LINE, labels=labels,
                       series=[ReportChartSeries(name=name, data=data)])


def count_by(values: list[str | None], unknown: str = "Unspecified") -> dict[str, int]:
    buckets: dict[str, int] = {}
    for value in values:
        key = (value or "").strip() or unknown
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


def sorted_buckets(buckets: dict[str, int], numeric_keys: bool = False) -> list[tuple[str, int]]:
    """Stable bucket ordering: numeric keys ascending (years), else count desc,
    label asc (the densest-first convention of every module dashboard)."""
    if numeric_keys:
        return sorted(buckets.items(), key=lambda item: (not item[0].isdigit(), item[0]))
    return sorted(buckets.items(), key=lambda item: (-item[1], item[0].casefold()))


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def title_case(raw: str | None) -> str:
    """``invited_talk`` -> ``Invited Talk`` (frontend titleCase parity)."""
    if not raw:
        return "—"
    return " ".join(word.capitalize() for word in str(raw).replace("_", " ").split())
