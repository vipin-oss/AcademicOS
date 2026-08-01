import type { ReactNode } from "react";
import { titleCase } from "@/lib/utils";
import { Badge } from "@/components/features/documents/DocumentBadge";
import type { PipelineStage, PublicationStatus, Quartile } from "@/types";

/**
 * Publication badges. The badge shell (`Badge`) and the status styling are
 * REUSED from the Documents module (single implementation, same status
 * vocabulary); only the publication-specific chips live here.
 */

const STATUS_STYLES: Record<PublicationStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function PublicationStatusBadge({ status }: { status: PublicationStatus }) {
  return (
    <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

export function PublicationTypeBadge({ type }: { type: string }) {
  return (
    <Badge className="bg-[var(--accent-subtle)] text-[var(--accent)]">
      <span className="sr-only">Type: </span>
      {titleCase(type)}
    </Badge>
  );
}

const QUARTILE_STYLES: Record<Quartile, string> = {
  Q1: "bg-[var(--success-subtle)] text-[var(--success)]",
  Q2: "bg-[var(--info-subtle)] text-[var(--info)]",
  Q3: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  Q4: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function QuartileBadge({ quartile }: { quartile: Quartile }) {
  return (
    <Badge className={QUARTILE_STYLES[quartile]}>
      <span className="sr-only">Quartile </span>
      {quartile}
    </Badge>
  );
}

const PIPELINE_STYLES: Partial<Record<PipelineStage, string>> = {
  idea: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  internal_review: "bg-[var(--info-subtle)] text-[var(--info)]",
  submitted: "bg-[var(--info-subtle)] text-[var(--info)]",
  under_review: "bg-[var(--info-subtle)] text-[var(--info)]",
  revision: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  accepted: "bg-[var(--success-subtle)] text-[var(--success)]",
  published: "bg-[var(--success-subtle)] text-[var(--success)]",
  post_publication: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function PipelineStageBadge({ stage }: { stage: PipelineStage }) {
  return (
    <Badge className={PIPELINE_STYLES[stage] ?? "bg-[var(--bg-hover)] text-[var(--text-secondary)]"}>
      <span className="sr-only">Pipeline stage: </span>
      {titleCase(stage)}
    </Badge>
  );
}

export function IndexingChips({ indexing }: { indexing: string[] }) {
  if (!indexing?.length) return null;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {indexing.map((index) => (
        <Badge key={index} className="bg-[var(--bg-hover)] text-[var(--text-secondary)]">
          {index}
        </Badge>
      ))}
    </span>
  );
}

/** Small labelled chip list (keywords / tags / collections). */
export function ChipList({ items }: { items?: string[] | null; }): ReactNode {
  if (!items?.length) {
    return <span className="text-[var(--text-tertiary)]">—</span>;
  }
  return (
    <span className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]"
        >
          {item}
        </span>
      ))}
    </span>
  );
}
