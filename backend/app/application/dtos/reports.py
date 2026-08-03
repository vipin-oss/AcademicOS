"""Reports & Analytics DTOs — the uniform report contract.

Read-only module: every report is *computed* from the existing modules' data
(Universal Objects + metadata + relationships) at request time — nothing is
stored twice (the module objective, PART 0). The contract is uniform so the
frontend renders every report with one component family and the export use
case (PART 11) serialises any report to CSV / XLSX / PDF from the same shape:

- ``ReportKpi``    — headline number cards (label + preformatted string value)
- ``ReportTable``  — a titled table; all cells are display strings; optional
  per-cell ``hrefs`` let the UI link rows back to the source module without
  the exporter needing to understand links (export ignores hrefs by design)
- ``ReportChart``  — a bar/line chart (labels + named numeric series)
- ``ReportView``   — kind + title + generated-at + applied filters + the
  kpi/table/chart lists; also the exact payload the exporters consume

Filters (PART 12) travel as one ``ReportFilters`` object; each kind documents
which of them it honours (helpers drop the rest, recording the applied subset
in ``ReportView.applied_filters`` so the workspace + export header show the
truth about what was filtered).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Catalogues (PART 2..10 kinds + PART 11 formats)
# ---------------------------------------------------------------------------
REPORT_KINDS: tuple[str, ...] = (
    "publications",
    "research",
    "faculty",
    "students",
    "teaching",
    "finance",
    "events",
    "committees",
    "analytics",
)
REPORT_TITLES: dict[str, str] = {
    "publications": "Publications Report",
    "research": "Research Report",
    "faculty": "Faculty Report",
    "students": "Student Report",
    "teaching": "Teaching Report",
    "finance": "Finance Report",
    "events": "Events Report",
    "committees": "Committee Report",
    "analytics": "Analytics",
}

EXPORT_FORMATS: tuple[str, ...] = ("csv", "xlsx", "pdf")

# Chart kinds the (dependency-free) frontend SVG renderer supports.
CHART_BAR = "bar"
CHART_LINE = "line"
CHART_KINDS: tuple[str, ...] = (CHART_BAR, CHART_LINE)

# Which PART 12 filter keys each kind honours (documented + surfaced via
# applied_filters; the workspace renders the same pickers from this map).
ALL_FILTER_KEYS: tuple[str, ...] = (
    "year",
    "date_from",
    "date_to",
    "faculty_id",
    "student_id",
    "project_id",
    "grant_id",
    "department",
    "event_id",
    "committee_id",
)
FILTER_KEYS_BY_KIND: dict[str, tuple[str, ...]] = {
    "publications": (
        "year", "date_from", "date_to", "faculty_id", "project_id", "grant_id",
    ),
    "research": (
        "year", "date_from", "date_to", "project_id", "grant_id", "department",
    ),
    "faculty": ("faculty_id", "department", "year", "date_from", "date_to"),
    "students": ("student_id", "department", "year", "date_from", "date_to"),
    "teaching": ("year", "date_from", "date_to", "faculty_id"),
    "finance": ("year", "date_from", "date_to", "project_id", "grant_id", "department"),
    "events": (
        "year", "date_from", "date_to", "faculty_id", "department", "event_id",
    ),
    "committees": ("year", "date_from", "date_to", "faculty_id", "committee_id"),
    "analytics": (),
}

DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class ReportFilters:
    """PART 12 filter input. All optional; empty strings normalised to None."""

    year: int | None = None
    date_from: str | None = None  # ISO YYYY-MM-DD (inclusive)
    date_to: str | None = None    # ISO YYYY-MM-DD (inclusive)
    faculty_id: str | None = None
    student_id: str | None = None
    project_id: str | None = None
    grant_id: str | None = None
    department: str | None = None
    event_id: str | None = None
    committee_id: str | None = None


@dataclass(frozen=True)
class ReportKpi:
    label: str
    value: str


@dataclass(frozen=True)
class ReportTable:
    """A titled display table. ``rows[i]`` aligns with ``hrefs[i]`` per cell."""

    key: str
    title: str
    columns: tuple[str, ...]
    rows: list[list[str]]
    hrefs: list[list[str | None]] | None = None  # same shape as rows (frontend only)


@dataclass(frozen=True)
class ReportChartSeries:
    name: str
    data: list[float]


@dataclass(frozen=True)
class ReportChart:
    key: str
    title: str
    kind: str  # CHART_BAR | CHART_LINE
    labels: list[str]
    series: list[ReportChartSeries]


@dataclass(frozen=True)
class ReportView:
    """The full computed report — also the exporters' source payload."""

    kind: str
    title: str
    generated_at: str  # ISO datetime
    applied_filters: dict[str, str]
    kpis: list[ReportKpi] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)
    charts: list[ReportChart] = field(default_factory=list)


@dataclass(frozen=True)
class ReportsDashboard:
    """PART 1 headline cards (computed read, the events/finance precedent)."""

    total_publications: int
    total_projects: int
    total_grants: int
    total_students: int
    total_classes: int
    total_faculty: int
    total_committees: int
    total_events: int
    budget_approved: float
    budget_utilized: float
    budget_remaining: float


# ---------------------------------------------------------------------------
# Display formatting helpers (shared by every report builder + the exporters)
# ---------------------------------------------------------------------------
def _indian_grouping(digits: str) -> str:
    """1234567 -> "12,34,567" — en-IN grouping (last three, then twos)."""
    head, tail = digits[:-3], digits[-3:]
    if not head:
        return tail
    twos: list[str] = []
    while head:
        twos.append(head[-2:])
        head = head[:-2]
    return ",".join(reversed(twos)) + "," + tail


def fmt_int(value: int | float) -> str:
    """1 234 567 -> "12,34,567" (en-IN grouping, the platform convention)."""
    sign = "-" if value < 0 else ""
    return sign + _indian_grouping(str(abs(int(value))))


def fmt_money(value: float | None) -> str:
    """INR display, the finance convention (₹ + en-IN grouping, no decimals
    for whole amounts, two decimals otherwise)."""
    if value is None:
        return "—"
    rounded = round(float(value), 2)
    sign = "-" if rounded < 0 else ""
    whole, _, frac = f"{abs(rounded):.2f}".partition(".")
    grouped = _indian_grouping(whole)
    if rounded == int(rounded):
        return f"{sign}₹{grouped}"
    return f"{sign}₹{grouped}.{frac}"


def fmt_pct(numerator: float, denominator: float, suffix: str = "%") -> str:
    if not denominator:
        return "—"
    return f"{round(numerator / denominator * 100, 1):g}{suffix}"


def fmt_number(value: float, digits: int = 1) -> str:
    if value != value:  # NaN guard
        return "—"
    rounded = round(value, digits)
    return f"{rounded:g}"
