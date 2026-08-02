import { titleCase } from "@/lib/utils";
import { studentTypeLabel } from "@/lib/students/constants";
import { Badge } from "@/components/features/documents/DocumentBadge";
import type { StudentStatus, StudentTypeValue } from "@/types";

/**
 * Student badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the status styles follow the frozen
 * vocabulary (same mapping as Publications).
 */

const STATUS_STYLES: Record<StudentStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function StudentStatusBadge({ status }: { status: StudentStatus }) {
  return (
    <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

const TYPE_STYLES: Record<StudentTypeValue, string> = {
  ug: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  pg: "bg-[var(--info-subtle)] text-[var(--info)]",
  phd: "bg-[var(--success-subtle)] text-[var(--success)]",
  alumni: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function StudentTypeBadge({ type }: { type: string }) {
  return (
    <Badge className={TYPE_STYLES[type as StudentTypeValue] ?? TYPE_STYLES.ug}>
      <span className="sr-only">Student type: </span>
      {studentTypeLabel(type)}
    </Badge>
  );
}
