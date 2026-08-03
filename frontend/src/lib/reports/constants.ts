/**
 * Reports & Analytics frontend constants — mirrors the backend
 * `application/dtos/reports.py` catalogue (kinds, honoured PART 12 filters,
 * page sizes). Icons are referenced by lucide component in the page chrome.
 */
import type { ReportFilters } from "@/types";

export const REPORT_KINDS = [
  {
    key: "publications",
    title: "Publications Report",
    description: "Year, journal, conference, type, author, project and grant lenses.",
    filters: ["year", "date_from", "date_to", "faculty_id", "project_id", "grant_id"],
  },
  {
    key: "research",
    title: "Research Report",
    description: "Active and completed projects, timeline, grants, budgets, publications and teams.",
    filters: ["year", "date_from", "date_to", "project_id", "grant_id", "department"],
  },
  {
    key: "faculty",
    title: "Faculty Report",
    description: "Member profiles — publications, projects, grants, teaching, events, committees.",
    filters: ["faculty_id", "department", "year", "date_from", "date_to"],
  },
  {
    key: "students",
    title: "Student Report",
    description: "Attendance, assignment, marks and grade summaries per student.",
    filters: ["student_id", "department", "year", "date_from", "date_to"],
  },
  {
    key: "teaching",
    title: "Teaching Report",
    description: "Class summary, attendance percentage, assignment statistics, gradebook.",
    filters: ["year", "date_from", "date_to", "faculty_id"],
  },
  {
    key: "finance",
    title: "Finance Report",
    description: "Budget utilization, vendor summary, purchases and assets.",
    filters: ["year", "date_from", "date_to", "project_id", "grant_id", "department"],
  },
  {
    key: "events",
    title: "Events Report",
    description: "Events organized and attended, participation, certificates, workshops, conferences.",
    filters: ["year", "date_from", "date_to", "faculty_id", "department", "event_id"],
  },
  {
    key: "committees",
    title: "Committee Report",
    description: "Meetings, attendance and action items — pending and completed.",
    filters: ["year", "date_from", "date_to", "faculty_id", "committee_id"],
  },
  {
    key: "analytics",
    title: "Analytics",
    description: "Year-wise trends — publications, events, budget, teaching load, attendance.",
    filters: [],
  },
] as const;

export type ReportKind = (typeof REPORT_KINDS)[number]["key"];

export function reportKind(key: string) {
  return REPORT_KINDS.find((kind) => kind.key === key);
}

/** PART 11 export formats (backend stdlib writers). */
export const EXPORT_FORMATS = [
  { key: "pdf", label: "PDF" },
  { key: "csv", label: "CSV" },
  { key: "xlsx", label: "Excel" },
] as const;

/** Year picker span (calendar years around the current one — the events
 * module's year-select convention). */
export const YEAR_OPTIONS: string[] = (() => {
  const current = new Date().getFullYear();
  const years: string[] = [];
  for (let year = current + 1; year >= current - 10; year -= 1) years.push(String(year));
  return years;
})();

/** Drop-empty helper for query strings (the events listQuery convention). */
export function cleanFilters(filters: ReportFilters): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      out[key] = String(value).trim();
    }
  }
  return out;
}
