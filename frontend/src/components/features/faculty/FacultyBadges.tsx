import { Badge } from "@/components/features/documents/DocumentBadge";
import { employmentTypeLabel } from "@/lib/faculty/constants";
import { titleCase } from "@/lib/utils";
import type { FacultyEmploymentType } from "@/types";

/**
 * Faculty badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the universal Object status badge is the
 * Research module's `ResearchStatusBadge` (import it from there — no copy).
 */

const EMPLOYMENT_STYLES: Record<FacultyEmploymentType, string> = {
  regular: "bg-[var(--success-subtle)] text-[var(--success)]",
  contract: "bg-[var(--info-subtle)] text-[var(--info)]",
  visiting: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  adjunct: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function EmploymentTypeBadge({ type }: { type: string }) {
  return (
    <Badge className={EMPLOYMENT_STYLES[type as FacultyEmploymentType] ?? EMPLOYMENT_STYLES.contract}>
      <span className="sr-only">Employment: </span>
      {employmentTypeLabel(type)}
    </Badge>
  );
}

export function StudentTypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    ug: "bg-[var(--info-subtle)] text-[var(--info)]",
    pg: "bg-[var(--accent-subtle)] text-[var(--accent)]",
    phd: "bg-[var(--success-subtle)] text-[var(--success)]",
    alumni: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  };
  return (
    <Badge className={styles[type] ?? styles.ug}>
      <span className="sr-only">Student type: </span>
      {type === "ug" || type === "pg" ? type.toUpperCase() : titleCase(type)}
    </Badge>
  );
}

const ROLE_LABELS: Record<string, string> = {
  leads: "PI",
  co_leads: "Co-PI",
  works_in: "Team",
  supervised_by: "Supervisor",
  advised_by: "Co-Supervisor",
  member_of: "Member",
  taught_by: "Teacher",
  authored_by: "Author",
};

/** Human label for a relationship kind (PI / Co-PI / Team / Supervisor …). */
export function roleLabel(kind: string): string {
  return ROLE_LABELS[kind] ?? titleCase(kind.replace(/_/g, " "));
}
