import type {
  ActionPriority,
  ActionStatus,
  AgendaItemPriority,
  AgendaItemStatus,
  AttendanceStatus,
  CommitteeLinkGroup,
  CommitteeRole,
  MeetingMode,
} from "@/types";

/**
 * Committees & Meetings constants. The vocabularies mirror the backend
 * (`app/application/dtos/committee.py`) one-to-one — keep them in sync.
 */

/** PART 1 committee types (the named nine; "custom" allows free text). */
export const COMMITTEE_TYPES: { value: string; label: string }[] = [
  { value: "purchase", label: "Purchase" },
  { value: "research", label: "Research" },
  { value: "drc", label: "DRC" },
  { value: "bos", label: "BoS" },
  { value: "academic_council", label: "Academic Council" },
  { value: "finance", label: "Finance" },
  { value: "examination", label: "Examination" },
  { value: "selection", label: "Selection" },
  { value: "iqac", label: "IQAC" },
  { value: "custom", label: "Custom" },
];

export function committeeTypeLabel(value: string | null | undefined): string {
  const found = COMMITTEE_TYPES.find((type) => type.value === value);
  if (found) return found.label;
  return (value ?? "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "—";
}

/** PART 2 member roles (closed vocabulary). */
export const COMMITTEE_ROLES: { value: CommitteeRole; label: string }[] = [
  { value: "chairperson", label: "Chairperson" },
  { value: "convener", label: "Convener" },
  { value: "coordinator", label: "Coordinator" },
  { value: "member", label: "Member" },
  { value: "external_expert", label: "External Expert" },
  { value: "student_member", label: "Student Member" },
  { value: "observer", label: "Observer" },
  { value: "nominee", label: "Nominee" },
];

export function committeeRoleLabel(value: string | null | undefined): string {
  const found = COMMITTEE_ROLES.find((role) => role.value === value);
  if (found) return found.label;
  return (value ?? "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "—";
}

/** PART 3 meeting modes. */
export const MEETING_MODES: { value: MeetingMode; label: string }[] = [
  { value: "offline", label: "Offline" },
  { value: "online", label: "Online" },
  { value: "hybrid", label: "Hybrid" },
];

/** PART 4 agenda vocabulary. */
export const AGENDA_PRIORITIES: { value: AgendaItemPriority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const AGENDA_ITEM_STATUSES: { value: AgendaItemStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "discussed", label: "Discussed" },
  { value: "decided", label: "Decided" },
  { value: "deferred", label: "Deferred" },
];

/** Meeting attendance vocabulary. */
export const ATTENDANCE_STATUSES: { value: AttendanceStatus; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "leave", label: "On Leave" },
];

/** PART 5 action-tracker vocabulary. */
export const ACTION_PRIORITIES: { value: ActionPriority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const ACTION_STATUSES: { value: ActionStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In Progress" },
  { value: "done", label: "Done" },
];

/** PART 7 research-link groups (written on the committee aggregate). */
export const COMMITTEE_LINK_GROUPS: { value: CommitteeLinkGroup; label: string }[] = [
  { value: "projects", label: "Research Projects" },
  { value: "grants", label: "Grants" },
  { value: "students", label: "Students" },
  { value: "publications", label: "Publications" },
];

export const DEFAULT_COMMITTEE_PAGE_SIZE = 20;

/** Registry status filter (universal object status). */
export const COMMITTEE_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
  { value: "archived", label: "Archived" },
];
