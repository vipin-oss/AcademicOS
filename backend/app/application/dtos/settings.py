"""DTOs for the Settings & Preferences module.

Mirrors ``dtos/productivity.py``: option catalogues as ``(code, label)``
tuples, per-section input dataclasses (``None`` = untouched, the verbatim
merge doctrine), and section/document outputs. Settings metadata keys are
``"<section>.<field>"`` on the single ``ObjectType.SETTINGS`` object — the
catalogue below is the single source of truth shared by validators, use
cases and mappers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Section codes (PART 1..8, 10) — the sections of the settings document.
# ---------------------------------------------------------------------------
SECTION_PROFILE = "profile"
SECTION_APPEARANCE = "appearance"
SECTION_ACADEMIC = "academic"
SECTION_NOTIFICATIONS = "notifications"
SECTION_DASHBOARD = "dashboard"
SECTION_SEARCH = "search"
SECTION_PRIVACY = "privacy"
SECTION_AI = "ai"

SECTION_CODES: tuple[str, ...] = (
    SECTION_PROFILE,
    SECTION_APPEARANCE,
    SECTION_ACADEMIC,
    SECTION_NOTIFICATIONS,
    SECTION_DASHBOARD,
    SECTION_SEARCH,
    SECTION_PRIVACY,
    SECTION_AI,
)

KEY_SETTINGS_SCOPE = "settings.scope"
SETTINGS_TITLE = "User Settings"
PHOTO_STORAGE_KEY = "settings/profile_photo"
EXPORT_VERSION = 1
KEY_HAS_PHOTO = "_photo.has_photo"
KEY_PHOTO_MIME = "_photo.mime"
KEY_PHOTO_NAME = "_photo.name"
PHOTO_MAX_BYTES = 2_000_000
PHOTO_MIME_TYPES: tuple[str, ...] = ("image/png", "image/jpeg", "image/webp", "image/gif")

# ---------------------------------------------------------------------------
# Option catalogues (code, label) — validated against the CODES tuples.
# ---------------------------------------------------------------------------
THEMES: tuple[tuple[str, str], ...] = (
    ("light", "Light"),
    ("dark", "Dark"),
    ("system", "System"),
)
THEME_CODES = tuple(code for code, _ in THEMES)

DATE_FORMATS: tuple[tuple[str, str], ...] = (
    ("yyyy-mm-dd", "YYYY-MM-DD (ISO)"),
    ("dd-mm-yyyy", "DD-MM-YYYY"),
    ("dd/mm/yyyy", "DD/MM/YYYY"),
    ("mm/dd/yyyy", "MM/DD/YYYY"),
)
DATE_FORMAT_CODES = tuple(code for code, _ in DATE_FORMATS)

REMINDER_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("none", "No reminder"),
    ("same_day", "Same day"),
    ("one_day_before", "One day before"),
    ("one_week_before", "One week before"),
)
REMINDER_DEFAULT_CODES = tuple(code for code, _ in REMINDER_DEFAULTS)

PRIORITY_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
)
PRIORITY_DEFAULT_CODES = tuple(code for code, _ in PRIORITY_DEFAULTS)

CALENDAR_VIEW_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("day", "Day"),
    ("week", "Week"),
    ("month", "Month"),
    ("agenda", "Agenda"),
)
CALENDAR_VIEW_DEFAULT_CODES = tuple(code for code, _ in CALENDAR_VIEW_DEFAULTS)

DASHBOARD_VIEWS: tuple[tuple[str, str], ...] = (
    ("grid", "Grid"),
    ("list", "List"),
    ("compact", "Compact"),
)
DASHBOARD_VIEW_CODES = tuple(code for code, _ in DASHBOARD_VIEWS)

MODULE_CODES: tuple[str, ...] = (
    "objects", "documents", "publications", "students", "teaching",
    "research", "faculty", "committees", "finance", "events",
    "reports", "productivity",
)

WIDGET_CODES: tuple[str, ...] = (
    "productivity_cards", "reminders", "calendar", "tasks",
    "notifications", "reports_overview", "events_overview",
)

SEARCH_SCOPES: tuple[tuple[str, str], ...] = (
    ("all", "Everything"),
    ("objects", "Objects"),
    ("documents", "Documents"),
    ("publications", "Publications"),
    ("students", "Students"),
    ("teaching", "Teaching"),
    ("research", "Research"),
    ("faculty", "Faculty"),
    ("committees", "Committees"),
    ("finance", "Finance"),
    ("events", "Events"),
    ("reports", "Reports"),
    ("productivity", "Productivity"),
)
SEARCH_SCOPE_CODES = tuple(code for code, _ in SEARCH_SCOPES)

AI_REPORT_FORMATS: tuple[tuple[str, str], ...] = (
    ("", "— not set —"),
    ("pdf", "PDF"),
    ("excel", "Excel"),
    ("csv", "CSV"),
)
AI_REPORT_FORMAT_CODES = tuple(code for code, _ in AI_REPORT_FORMATS)

AI_LAYOUTS: tuple[tuple[str, str], ...] = (
    ("", "— not set —"),
    ("default", "Default"),
    ("compact", "Compact"),
    ("wide", "Wide"),
)
AI_LAYOUT_CODES = tuple(code for code, _ in AI_LAYOUTS)

SEARCH_RECENT_LIMIT_MIN = 0
SEARCH_RECENT_LIMIT_MAX = 50

# ---------------------------------------------------------------------------
# Field specs — (type, default) per section field. Types: "str" | "bool" |
# "int" | "list" | "map". Absence of a metadata entry == the default, so a
# fresh object reads back as factory defaults (get_or_create stays minimal).
# ---------------------------------------------------------------------------
SECTION_FIELD_SPECS: dict[str, tuple[tuple[str, tuple[str, object]], ...]] = {
    SECTION_PROFILE: (
        ("name", ("str", "")),
        ("email", ("str", "")),
        ("designation", ("str", "")),
        ("department", ("str", "")),
        ("institution", ("str", "")),
        ("biography", ("str", "")),
    ),
    SECTION_APPEARANCE: (
        ("theme", ("str", "system")),
        # Future-ready: a named custom theme — stored, inactive until themes land.
        ("custom_theme", ("str", "")),
    ),
    SECTION_ACADEMIC: (
        ("default_session", ("str", "")),
        ("default_department", ("str", "")),
        ("default_programme", ("str", "")),
        ("default_semester", ("str", "")),
        ("default_timezone", ("str", "")),
        ("date_format", ("str", "yyyy-mm-dd")),
    ),
    SECTION_NOTIFICATIONS: (
        ("enabled", ("bool", True)),
        ("reminder_default", ("str", "same_day")),
        ("priority_default", ("str", "medium")),
        ("calendar_default_view", ("str", "month")),
        ("calendar_default_sources", ("list", [])),
    ),
    SECTION_DASHBOARD: (
        ("default_landing_page", ("str", "/")),
        ("favorite_modules", ("list", [])),
        ("widget_visibility", ("map", {})),
        ("default_view", ("str", "grid")),
    ),
    SECTION_SEARCH: (
        ("default_scope", ("str", "all")),
        ("recent_searches_limit", ("int", 10)),
        ("saved_filters", ("map", {})),
    ),
    SECTION_PRIVACY: (
        ("remember_last_module", ("bool", True)),
        ("reduce_motion", ("bool", False)),
        ("session_filter_memory", ("bool", True)),
        ("session_page_size", ("int", 20)),
    ),
    SECTION_AI: (
        ("preferred_writing_style", ("str", "")),
        ("preferred_report_format", ("str", "")),
        ("preferred_dashboard_layout", ("str", "")),
    ),
}


# ---------------------------------------------------------------------------
# Inputs (None = untouched — the verbatim merge doctrine)
# ---------------------------------------------------------------------------
@dataclass
class SectionUpdateInput:
    """Generic per-section update: only provided keys are written.

    The 8 section commands carry this single shape (section code + typed
    patch map); validators pin every provided key to its spec.
    """
    section: str
    values: dict[str, object] = field(default_factory=dict)
    updated_by: str = "system"


@dataclass
class ImportSettingsInput:
    sections: dict[str, dict[str, object]] = field(default_factory=dict)
    updated_by: str = "system"


@dataclass
class ResetSettingsInput:
    sections: list[str] | None = None  # None = every section
    updated_by: str = "system"


@dataclass
class SetProfilePhotoInput:
    file_name: str
    content: bytes
    mime_type: str
    updated_by: str = "system"


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass
class SettingsDocumentOutput:
    sections: dict[str, dict[str, object]]
    has_photo: bool
    photo_name: str | None
    photo_url: str | None
    updated_at: str | None


@dataclass
class SettingsSectionOutput:
    section: str
    values: dict[str, object]


@dataclass
class ExportSettingsOutput:
    version: int
    app: str
    exported_at: str
    sections: dict[str, dict[str, object]]


@dataclass
class ProfilePhotoOutput:
    file_name: str
    mime_type: str
    size_bytes: int
    content: bytes | None = None  # only filled by the read path
