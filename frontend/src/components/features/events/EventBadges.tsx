import { Badge } from "@/components/features/documents/DocumentBadge";
import { eventTypeLabel } from "@/lib/events/constants";
import { titleCase } from "@/lib/utils";
import type {
  EventMode,
  EventPriority,
  EventStatus,
  ParticipationRole,
  PresentationRelation,
  ResearchObjectStatus,
} from "@/types";

/**
 * Events badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the status styles follow the frozen
 * vocabulary (same mapping as Finance/Committees/Research/Publications).
 */

const UNIVERSAL_STATUS_STYLES: Record<ResearchObjectStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function UniversalStatusBadge({ status }: { status: ResearchObjectStatus }) {
  return (
    <Badge className={UNIVERSAL_STATUS_STYLES[status] ?? UNIVERSAL_STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

const EVENT_STATUS_STYLES: Record<string, string> = {
  planned: "bg-[var(--info-subtle)] text-[var(--info)]",
  ongoing: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  postponed: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  completed: "bg-[var(--success-subtle)] text-[var(--success)]",
  cancelled: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function EventStatusBadge({ status }: { status: EventStatus }) {
  return (
    <Badge className={EVENT_STATUS_STYLES[status] ?? EVENT_STATUS_STYLES.planned}>
      <span className="sr-only">Event status: </span>
      {titleCase(status)}
    </Badge>
  );
}

export function EventTypeBadge({ type }: { type: string | null | undefined }) {
  if (!type) return <>—</>;
  return (
    <Badge className="bg-[var(--accent-subtle)] text-[var(--accent)]">
      <span className="sr-only">Event type: </span>
      {eventTypeLabel(type)}
    </Badge>
  );
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  medium: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  low: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function EventPriorityBadge({ priority }: { priority: EventPriority }) {
  return (
    <Badge className={PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.low}>
      <span className="sr-only">Priority: </span>
      {titleCase(priority)}
    </Badge>
  );
}

const MODE_STYLES: Record<string, string> = {
  online: "bg-[var(--info-subtle)] text-[var(--info)]",
  offline: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  hybrid: "bg-[var(--accent-subtle)] text-[var(--accent)]",
};

export function EventModeBadge({ mode }: { mode: EventMode }) {
  return (
    <Badge className={MODE_STYLES[mode] ?? MODE_STYLES.offline}>
      <span className="sr-only">Mode: </span>
      {titleCase(mode)}
    </Badge>
  );
}

export function ParticipationRoleBadge({ role }: { role: ParticipationRole }) {
  return (
    <Badge className="bg-[var(--info-subtle)] text-[var(--info)]">
      <span className="sr-only">Role: </span>
      {titleCase(role)}
    </Badge>
  );
}

const RELATION_STYLES: Record<string, string> = {
  presented_paper: "bg-[var(--success-subtle)] text-[var(--success)]",
  published_proceedings: "bg-[var(--info-subtle)] text-[var(--info)]",
  best_paper_award: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  poster_presentation: "bg-[var(--accent-subtle)] text-[var(--accent)]",
};

export function PresentationRelationBadge({
  relation,
}: {
  relation: PresentationRelation;
}) {
  return (
    <Badge className={RELATION_STYLES[relation] ?? RELATION_STYLES.presented_paper}>
      <span className="sr-only">Relation: </span>
      {titleCase(relation)}
    </Badge>
  );
}
