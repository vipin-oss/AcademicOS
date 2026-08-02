import { Badge } from "@/components/features/documents/DocumentBadge";
import { lifecycleLabel } from "@/lib/research/constants";
import { titleCase } from "@/lib/utils";
import type {
  InstallmentStatus,
  MilestoneStatus,
  ProjectLifecycleStatus,
  ProjectPriority,
  ResearchObjectStatus,
} from "@/types";

/**
 * Research badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the status styles follow the frozen
 * vocabulary (same mapping as Publications/Students).
 */

const UNIVERSAL_STATUS_STYLES: Record<ResearchObjectStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function ResearchStatusBadge({ status }: { status: ResearchObjectStatus }) {
  return (
    <Badge className={UNIVERSAL_STATUS_STYLES[status] ?? UNIVERSAL_STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

const LIFECYCLE_STYLES: Record<ProjectLifecycleStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  proposal_submitted: "bg-[var(--info-subtle)] text-[var(--info)]",
  under_review: "bg-[var(--info-subtle)] text-[var(--info)]",
  approved: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  funded: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  on_hold: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  completed: "bg-[var(--success-subtle)] text-[var(--success)]",
  closed: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function LifecycleStatusBadge({ status }: { status: ProjectLifecycleStatus }) {
  return (
    <Badge className={LIFECYCLE_STYLES[status] ?? LIFECYCLE_STYLES.draft}>
      <span className="sr-only">Lifecycle: </span>
      {lifecycleLabel(status)}
    </Badge>
  );
}

const PRIORITY_STYLES: Record<ProjectPriority, string> = {
  high: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  medium: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  low: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <Badge className={PRIORITY_STYLES[priority as ProjectPriority] ?? PRIORITY_STYLES.low}>
      <span className="sr-only">Priority: </span>
      {titleCase(priority)}
    </Badge>
  );
}

const MILESTONE_STYLES: Record<MilestoneStatus, string> = {
  pending: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  in_progress: "bg-[var(--info-subtle)] text-[var(--info)]",
  done: "bg-[var(--success-subtle)] text-[var(--success)]",
};

export function MilestoneStatusBadge({ status }: { status: MilestoneStatus }) {
  return (
    <Badge className={MILESTONE_STYLES[status] ?? MILESTONE_STYLES.pending}>
      <span className="sr-only">Milestone: </span>
      {titleCase(status.replace("_", " "))}
    </Badge>
  );
}

const INSTALLMENT_STYLES: Record<InstallmentStatus, string> = {
  released: "bg-[var(--success-subtle)] text-[var(--success)]",
  scheduled: "bg-[var(--info-subtle)] text-[var(--info)]",
};

export function InstallmentStatusBadge({ status }: { status: InstallmentStatus }) {
  return (
    <Badge className={INSTALLMENT_STYLES[status] ?? INSTALLMENT_STYLES.released}>
      <span className="sr-only">Installment: </span>
      {titleCase(status)}
    </Badge>
  );
}
