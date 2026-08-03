/** Shared calendar utilities + source cosmetics for the Productivity Hub. */

export const SOURCE_LABELS: Record<string, string> = {
  events: "Events",
  committee_meetings: "Committee Meetings",
  research_projects: "Research Projects",
  grant_milestones: "Grant Milestones",
  teaching: "Teaching",
  assignments: "Assignments",
  attendance_sessions: "Attendance",
  finance_due: "Finance Due",
  reports_due: "Reports Due",
  personal: "Personal",
};

/** Dot colours per source (inline styles — zero new dependencies). */
export const SOURCE_COLORS: Record<string, string> = {
  events: "#7c3aed",
  committee_meetings: "#0891b2",
  research_projects: "#2563eb",
  grant_milestones: "#d97706",
  teaching: "#059669",
  assignments: "#dc2626",
  attendance_sessions: "#6d28d9",
  finance_due: "#b45309",
  reports_due: "#be185d",
  personal: "#0f766e",
};

export const SOURCE_ORDER = Object.keys(SOURCE_LABELS);

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export function sourceColor(source: string): string {
  return SOURCE_COLORS[source] ?? "var(--accent)";
}

// ---------------------------------------------------------------------------
// Date maths (ISO-first, no date library on the frozen dependency set)
// ---------------------------------------------------------------------------
export function todayIso(): string {
  const now = new Date();
  return toIso(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

export function toIso(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function parseIso(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(iso: string, days: number): string {
  const base = parseIso(iso);
  base.setDate(base.getDate() + days);
  return toIso(base.getFullYear(), base.getMonth() + 1, base.getDate());
}

export function startOfMonth(iso: string): string {
  return `${iso.slice(0, 8)}01`;
}

export function startOfWeek(iso: string): string {
  const base = parseIso(iso);
  const day = base.getDay(); // 0=Sun
  const offset = (day + 6) % 7; // Monday-first grid
  return addDays(iso, -offset);
}

export function datesBetween(from: string, to: string): string[] {
  const out: string[] = [];
  let cursor = from;
  while (cursor <= to) {
    out.push(cursor);
    cursor = addDays(cursor, 1);
  }
  return out;
}

export function monthMatrix(iso: string): string[][] {
  /** Monday-first weeks covering the whole month of `iso`. */
  const first = startOfMonth(iso);
  const gridStart = startOfWeek(first);
  const weeks: string[][] = [];
  let cursor = gridStart;
  for (let w = 0; w < 6; w += 1) {
    const week: string[] = [];
    for (let d = 0; d < 7; d += 1) {
      week.push(cursor);
      cursor = addDays(cursor, 1);
    }
    weeks.push(week);
    if (week[6].slice(5, 7) !== iso.slice(5, 7) && cursor.slice(5, 7) !== iso.slice(5, 7)) {
      break; // stop once we've walked past the month
    }
  }
  return weeks;
}

export function formatDay(iso: string): string {
  return parseIso(iso).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export function formatLong(iso: string): string {
  return parseIso(iso).toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
