/**
 * Option catalogues for the Settings & Preferences module — mirror
 * `application/dtos/settings.py` (THEMES / DATE_FORMATS / REMINDER_DEFAULTS /
 * PRIORITY_DEFAULTS / CALENDAR_VIEW_DEFAULTS / DASHBOARD_VIEWS / MODULE_CODES /
 * WIDGET_CODES / SEARCH_SCOPES / AI_*) one-to-one, same doctrine as
 * `lib/productivity/constants.ts`. TIMEZONES / LANDING_PAGES are curated UI
 * conveniences (the backend accepts any ≤200-char string / any `/`-route).
 */

export const THEMES = [
  { value: "light", label: "Light", description: "Always use the light interface." },
  { value: "dark", label: "Dark", description: "Always use the dark interface." },
  {
    value: "system",
    label: "System",
    description: "Follow the operating-system appearance automatically.",
  },
] as const;

export const DATE_FORMATS = [
  { value: "yyyy-mm-dd", label: "YYYY-MM-DD (ISO)" },
  { value: "dd-mm-yyyy", label: "DD-MM-YYYY" },
  { value: "dd/mm/yyyy", label: "DD/MM/YYYY" },
  { value: "mm/dd/yyyy", label: "MM/DD/YYYY" },
] as const;

export const REMINDER_DEFAULTS = [
  { value: "none", label: "No reminder" },
  { value: "same_day", label: "Same day" },
  { value: "one_day_before", label: "One day before" },
  { value: "one_week_before", label: "One week before" },
] as const;

export const PRIORITY_DEFAULTS = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
] as const;

export const CALENDAR_VIEW_DEFAULTS = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "agenda", label: "Agenda" },
] as const;

export const DASHBOARD_VIEWS = [
  { value: "grid", label: "Grid" },
  { value: "list", label: "List" },
  { value: "compact", label: "Compact" },
] as const;

/** The 12 business modules (settings itself is excluded by the backend). */
export const MODULE_OPTIONS = [
  { value: "objects", label: "Objects" },
  { value: "documents", label: "Documents" },
  { value: "publications", label: "Publications" },
  { value: "students", label: "Students" },
  { value: "teaching", label: "Teaching" },
  { value: "research", label: "Research" },
  { value: "faculty", label: "Faculty" },
  { value: "committees", label: "Committees" },
  { value: "finance", label: "Finance" },
  { value: "events", label: "Events" },
  { value: "reports", label: "Reports" },
  { value: "productivity", label: "Productivity Hub" },
] as const;

export const WIDGET_OPTIONS = [
  { value: "productivity_cards", label: "Productivity cards" },
  { value: "reminders", label: "Reminders" },
  { value: "calendar", label: "Calendar" },
  { value: "tasks", label: "Tasks" },
  { value: "notifications", label: "Notifications" },
  { value: "reports_overview", label: "Reports overview" },
  { value: "events_overview", label: "Events overview" },
] as const;

export const SEARCH_SCOPES = [
  { value: "all", label: "Everything" },
  { value: "objects", label: "Objects" },
  { value: "documents", label: "Documents" },
  { value: "publications", label: "Publications" },
  { value: "students", label: "Students" },
  { value: "teaching", label: "Teaching" },
  { value: "research", label: "Research" },
  { value: "faculty", label: "Faculty" },
  { value: "committees", label: "Committees" },
  { value: "finance", label: "Finance" },
  { value: "events", label: "Events" },
  { value: "reports", label: "Reports" },
  { value: "productivity", label: "Productivity" },
] as const;

export const AI_REPORT_FORMATS = [
  { value: "", label: "— not set —" },
  { value: "pdf", label: "PDF" },
  { value: "excel", label: "Excel" },
  { value: "csv", label: "CSV" },
] as const;

export const AI_LAYOUTS = [
  { value: "", label: "— not set —" },
  { value: "default", label: "Default" },
  { value: "compact", label: "Compact" },
  { value: "wide", label: "Wide" },
] as const;

/** Calendar-source codes shared with the Productivity module (same codes). */
export const CALENDAR_SOURCE_OPTIONS = [
  { value: "events", label: "Events" },
  { value: "committee_meetings", label: "Committee meetings" },
  { value: "research_projects", label: "Research projects" },
  { value: "grant_milestones", label: "Grant milestones" },
  { value: "teaching", label: "Teaching" },
  { value: "assignments", label: "Assignments" },
  { value: "attendance_sessions", label: "Attendance sessions" },
  { value: "finance_due", label: "Finance dues" },
  { value: "reports_due", label: "Report deadlines" },
  { value: "personal", label: "Personal" },
] as const;

/** Curated IANA timezones — the backend stores any string, so this is a
 * convenience list, not an exhaustive constraint. "" means "not set". */
export const TIMEZONES = [
  { value: "", label: "— not set —" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST)" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Dubai", label: "Asia/Dubai" },
  { value: "Asia/Singapore", label: "Asia/Singapore" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Berlin", label: "Europe/Berlin" },
  { value: "America/New_York", label: "America/New_York" },
  { value: "America/Chicago", label: "America/Chicago" },
  { value: "America/Denver", label: "America/Denver" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles" },
  { value: "Australia/Sydney", label: "Australia/Sydney" },
] as const;

/** Curated app routes for the default landing page (all must start with "/"). */
export const LANDING_PAGES = [
  { value: "/", label: "Dashboard (home)" },
  { value: "/objects", label: "Objects" },
  { value: "/documents", label: "Documents" },
  { value: "/publications", label: "Publications" },
  { value: "/students", label: "Students" },
  { value: "/teaching", label: "Teaching" },
  { value: "/research", label: "Research" },
  { value: "/faculty", label: "Faculty" },
  { value: "/committees", label: "Committees" },
  { value: "/finance", label: "Finance" },
  { value: "/events", label: "Events" },
  { value: "/reports", label: "Reports" },
  { value: "/productivity", label: "Productivity Hub" },
] as const;

export const SESSION_PAGE_SIZES = [10, 20, 50, 100] as const;

export const RECENT_SEARCHES_MIN = 0;
export const RECENT_SEARCHES_MAX = 50;

export const PHOTO_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";
export const PHOTO_MAX_BYTES = 2_000_000;

export function moduleLabel(code: string): string {
  return MODULE_OPTIONS.find((option) => option.value === code)?.label ?? code;
}

export function widgetLabel(code: string): string {
  return WIDGET_OPTIONS.find((option) => option.value === code)?.label ?? code;
}
