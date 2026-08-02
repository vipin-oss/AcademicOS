import type {
  InstallmentStatus,
  MilestoneStatus,
  ProjectLifecycleStatus,
  ProjectPriority,
  ProjectTeamGroup,
} from "@/types";

/** The 9-state research lifecycle, in order, with human labels (PART 1). */
export const PROJECT_LIFECYCLE_STATUSES: {
  value: ProjectLifecycleStatus;
  label: string;
}[] = [
  { value: "draft", label: "Draft" },
  { value: "proposal_submitted", label: "Proposal Submitted" },
  { value: "under_review", label: "Under Review" },
  { value: "approved", label: "Approved" },
  { value: "funded", label: "Funded" },
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "closed", label: "Closed" },
];

export function lifecycleLabel(value: string | null | undefined): string {
  const found = PROJECT_LIFECYCLE_STATUSES.find((status) => status.value === value);
  if (found) return found.label;
  return (value ?? "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "—";
}

export const PROJECT_PRIORITIES: { value: ProjectPriority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const MILESTONE_STATUSES: { value: MilestoneStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "done", label: "Done" },
];

export const INSTALLMENT_STATUSES: { value: InstallmentStatus; label: string }[] = [
  { value: "released", label: "Released" },
  { value: "scheduled", label: "Scheduled" },
];

/** Common release schedules (free text allowed — these are the usual ones). */
export const RELEASE_SCHEDULES = [
  "annual",
  "semi-annual",
  "quarterly",
  "milestone-based",
  "one-time",
];

/** The team groups, with human labels (PART 1 / PART 4). */
export const PROJECT_TEAM_GROUPS: { value: ProjectTeamGroup; label: string }[] = [
  { value: "principal_investigators", label: "Principal Investigator" },
  { value: "co_investigators", label: "Co-PI(s)" },
  { value: "team_members", label: "Research Team" },
];

/** Well-known Indian funding agencies (PART 2 quick-add suggestions). */
export const COMMON_AGENCIES = [
  "DST — Department of Science & Technology",
  "CSIR — Council of Scientific & Industrial Research",
  "UGC — University Grants Commission",
  "ICSSR — Indian Council of Social Science Research",
  "DBT — Department of Biotechnology",
  "ICMR — Indian Council of Medical Research",
  "AICTE — All India Council for Technical Education",
  "SERB — Science & Engineering Research Board",
  "Haryana HSRF — Haryana State Research Foundation",
];

export const DEFAULT_PROJECT_PAGE_SIZE = 20;
export const DEFAULT_GRANT_PAGE_SIZE = 20;
export const DEFAULT_AGENCY_PAGE_SIZE = 50;

/** INR-first amount formatting (lakhs/crores read naturally in en-IN). */
export function formatAmount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `₹${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)}`;
}

/** "30 Jun 2026" — the registry date style used across the app. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value.length === 4 ? `${value}-01-01` : value.length === 7 ? `${value}-01` : value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Budget utilisation ratio for progress bars (0..1, null when unknown). */
export function utilizationRatio(utilized: number | null, approved: number | null): number | null {
  if (utilized == null || approved == null || approved <= 0) return null;
  return Math.min(1, Math.max(0, utilized / approved));
}
