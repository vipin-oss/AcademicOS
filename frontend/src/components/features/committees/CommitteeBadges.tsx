import { Badge } from "@/components/features/documents/DocumentBadge";
import { committeeRoleLabel, committeeTypeLabel } from "@/lib/committees/constants";
import { titleCase } from "@/lib/utils";
import type {
  ActionPriority,
  ActionStatus,
  AgendaItemPriority,
  AgendaItemStatus,
  AttendanceStatus,
  MeetingMode,
  ResearchObjectStatus,
} from "@/types";

/**
 * Committees badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the status styles follow the frozen
 * vocabulary (same mapping as Research/Publications/Students).
 */

const UNIVERSAL_STATUS_STYLES: Record<ResearchObjectStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function CommitteeStatusBadge({ status }: { status: ResearchObjectStatus }) {
  return (
    <Badge className={UNIVERSAL_STATUS_STYLES[status] ?? UNIVERSAL_STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

export function CommitteeTypeBadge({ type }: { type: string }) {
  return (
    <Badge className="bg-[var(--accent-subtle)] text-[var(--accent)]">
      <span className="sr-only">Type: </span>
      {committeeTypeLabel(type)}
    </Badge>
  );
}

const ROLE_STYLES: Record<string, string> = {
  chairperson: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  convener: "bg-[var(--info-subtle)] text-[var(--info)]",
  coordinator: "bg-[var(--info-subtle)] text-[var(--info)]",
  member: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  external_expert: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  student_member: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  observer: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  nominee: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function MemberRoleBadge({ role }: { role: string }) {
  return (
    <Badge className={ROLE_STYLES[role] ?? ROLE_STYLES.member}>
      <span className="sr-only">Role: </span>
      {committeeRoleLabel(role)}
    </Badge>
  );
}

const MODE_STYLES: Record<MeetingMode, string> = {
  offline: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  online: "bg-[var(--info-subtle)] text-[var(--info)]",
  hybrid: "bg-[var(--accent-subtle)] text-[var(--accent)]",
};

export function MeetingModeBadge({ mode }: { mode: MeetingMode }) {
  return (
    <Badge className={MODE_STYLES[mode] ?? MODE_STYLES.offline}>
      <span className="sr-only">Mode: </span>
      {titleCase(mode)}
    </Badge>
  );
}

const AGENDA_PRIORITY_STYLES: Record<AgendaItemPriority, string> = {
  high: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  medium: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  low: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function AgendaPriorityBadge({ priority }: { priority: string }) {
  return (
    <Badge
      className={
        AGENDA_PRIORITY_STYLES[priority as AgendaItemPriority] ?? AGENDA_PRIORITY_STYLES.low
      }
    >
      <span className="sr-only">Priority: </span>
      {titleCase(priority)}
    </Badge>
  );
}

const AGENDA_STATUS_STYLES: Record<AgendaItemStatus, string> = {
  pending: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  discussed: "bg-[var(--info-subtle)] text-[var(--info)]",
  decided: "bg-[var(--success-subtle)] text-[var(--success)]",
  deferred: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function AgendaStatusBadge({ status }: { status: string }) {
  return (
    <Badge
      className={AGENDA_STATUS_STYLES[status as AgendaItemStatus] ?? AGENDA_STATUS_STYLES.pending}
    >
      <span className="sr-only">Agenda item: </span>
      {titleCase(status || "pending")}
    </Badge>
  );
}

const ATTENDANCE_STYLES: Record<AttendanceStatus, string> = {
  present: "bg-[var(--success-subtle)] text-[var(--success)]",
  absent: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  leave: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function AttendanceStatusBadge({ status }: { status: AttendanceStatus }) {
  return (
    <Badge className={ATTENDANCE_STYLES[status] ?? ATTENDANCE_STYLES.leave}>
      <span className="sr-only">Attendance: </span>
      {titleCase(status)}
    </Badge>
  );
}

const ACTION_PRIORITY_STYLES: Record<ActionPriority, string> = {
  high: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  medium: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  low: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function ActionPriorityBadge({ priority }: { priority: string }) {
  return (
    <Badge
      className={
        ACTION_PRIORITY_STYLES[priority as ActionPriority] ?? ACTION_PRIORITY_STYLES.low
      }
    >
      <span className="sr-only">Priority: </span>
      {titleCase(priority)}
    </Badge>
  );
}

const ACTION_STATUS_STYLES: Record<ActionStatus, string> = {
  pending: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  in_progress: "bg-[var(--info-subtle)] text-[var(--info)]",
  done: "bg-[var(--success-subtle)] text-[var(--success)]",
};

export function ActionStatusBadge({ status }: { status: ActionStatus }) {
  return (
    <Badge className={ACTION_STATUS_STYLES[status] ?? ACTION_STATUS_STYLES.pending}>
      <span className="sr-only">Action: </span>
      {titleCase(status.replace("_", " "))}
    </Badge>
  );
}
