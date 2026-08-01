import type { ReactNode } from "react";
import { cn, titleCase } from "@/lib/utils";
import type { DocumentStatus } from "@/types";

const BASE =
  "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium";

const STATUS_STYLES: Record<DocumentStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn(BASE, className)} >{children}</span>;
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

export function DocumentTypeBadge({ type }: { type: string }) {
  return (
    <Badge className="bg-[var(--accent-subtle)] text-[var(--accent)]">
      <span className="sr-only">Type: </span>
      {titleCase(type)}
    </Badge>
  );
}

export function DocumentVersionBadge({ version }: { version: number }) {
  return (
    <Badge className="bg-[var(--bg-hover)] font-mono text-[var(--text-secondary)]">
      <span className="sr-only">Version </span>v{version}
    </Badge>
  );
}
