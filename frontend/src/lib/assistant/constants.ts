/**
 * Assistant frontend constants — mirrors the backend intent taxonomy
 * (`application/dtos/assistant.py` INTENT_GROUPS). Icons are lucide
 * components, following the sidebar/reports convention.
 */
import {
  BarChart3,
  Calendar,
  FlaskConical,
  LayoutDashboard,
  Presentation,
  Search,
  UsersRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface GroupMeta {
  icon: LucideIcon;
  blurb: string;
}

/** Display metadata per intent group (order = first appearance in home payload). */
export const GROUP_META: Record<string, GroupMeta> = {
  Dashboard: { icon: LayoutDashboard, blurb: "Today, deadlines, meetings, pending work" },
  Research: { icon: FlaskConical, blurb: "Publications, projects, grants, documents" },
  Teaching: { icon: Presentation, blurb: "Attendance, grading, classes, assignments" },
  Finance: { icon: Wallet, blurb: "Budgets, purchases, procurements" },
  Events: { icon: Calendar, blurb: "Workshops, participation, certificates" },
  Committees: { icon: UsersRound, blurb: "Meetings, action items, decisions" },
  Reports: { icon: BarChart3, blurb: "Report summaries and the catalogue" },
  Search: { icon: Search, blurb: "Natural-language knowledge-graph search" },
};

export function groupMeta(group: string): GroupMeta {
  return GROUP_META[group] ?? { icon: Search, blurb: "" };
}

/** Human labels for object_type badges on context cards. */
export const TYPE_LABELS: Record<string, string> = {
  publication: "Publication",
  research_project: "Project",
  grant: "Grant",
  funding_agency: "Agency",
  faculty: "Faculty",
  student: "Student",
  course: "Class",
  assignment: "Assignment",
  submission: "Submission",
  vendor: "Vendor",
  purchase: "Purchase",
  event: "Event",
  committee: "Committee",
  meeting: "Meeting",
  document: "Document",
  task: "Task",
  notification: "Notification",
  report: "Report",
};

export function typeLabel(objectType: string): string {
  return TYPE_LABELS[objectType] ?? objectType.replace(/_/g, " ");
}
