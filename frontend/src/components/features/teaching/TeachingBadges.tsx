import { titleCase } from "@/lib/utils";
import { assignmentTypeLabel, GRID_STATE_LABELS } from "@/lib/teaching/constants";
import { Badge } from "@/components/features/documents/DocumentBadge";
import type { AssignmentTypeValue, ClassStatus, SubmissionGridState } from "@/types";

/**
 * Teaching badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation, one status vocabulary).
 */

const STATUS_STYLES: Record<ClassStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function ClassStatusBadge({ status }: { status: ClassStatus }) {
  return (
    <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

const TYPE_STYLES: Record<AssignmentTypeValue, string> = {
  assignment: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  quiz: "bg-[var(--info-subtle)] text-[var(--info)]",
  internal_assessment: "bg-[var(--info-subtle)] text-[var(--info)]",
  mid_semester: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  end_semester: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function AssignmentTypeBadge({ type }: { type: string }) {
  return (
    <Badge className={TYPE_STYLES[type as AssignmentTypeValue] ?? TYPE_STYLES.assignment}>
      <span className="sr-only">Assessment type: </span>
      {assignmentTypeLabel(type)}
    </Badge>
  );
}

const GRID_STYLES: Record<SubmissionGridState, string> = {
  submitted: "bg-[var(--info-subtle)] text-[var(--info)]",
  late: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  pending: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  graded: "bg-[var(--success-subtle)] text-[var(--success)]",
};

export function GridStateBadge({ state }: { state: SubmissionGridState }) {
  return (
    <Badge className={GRID_STYLES[state]}>
      <span className="sr-only">Submission state: </span>
      {GRID_STATE_LABELS[state]}
    </Badge>
  );
}

/** Computed grade band chip (PART H) — A+..F straight from the gradebook. */
export function GradeBadge({ grade }: { grade: string }) {
  const style = grade.startsWith("A")
    ? "bg-[var(--success-subtle)] text-[var(--success)]"
    : grade.startsWith("B")
      ? "bg-[var(--info-subtle)] text-[var(--info)]"
      : grade === "F"
        ? "bg-[var(--danger-subtle)] text-[var(--danger)]"
        : "bg-[var(--warning-subtle)] text-[var(--warning)]";
  return (
    <Badge className={style}>
      <span className="sr-only">Grade: </span>
      {grade}
    </Badge>
  );
}

export function AttendanceFlagBadge({ below }: { below: boolean }) {
  return below ? (
    <Badge className="bg-[var(--danger-subtle)] text-[var(--danger)]">
      <span className="sr-only">Attendance: </span>Below 75%
    </Badge>
  ) : (
    <Badge className="bg-[var(--success-subtle)] text-[var(--success)]">
      <span className="sr-only">Attendance: </span>OK
    </Badge>
  );
}
