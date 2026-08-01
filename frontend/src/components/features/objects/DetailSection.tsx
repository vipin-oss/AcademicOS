import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Card wrapper for a detail-page section. */
export function Section({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5",
        className,
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/**
 * Section whose data the API does not expose yet. Explicit and honest — no
 * fake content, but it still shows what will live there.
 */
export function SectionPlaceholder({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface-2)] p-4 sm:p-5">
      <div className="mb-2 flex items-center gap-2">
        {icon ? <span className="text-[var(--text-tertiary)]">{icon}</span> : null}
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
        <span className="ml-auto rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
          Pending API
        </span>
      </div>
      <p className="text-sm text-[var(--text-tertiary)]">{description}</p>
    </section>
  );
}

/** Label / value line inside a section. */
export function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-[var(--border-subtle)] py-2 last:border-0 last:pb-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
      <dt className="shrink-0 text-[var(--text-tertiary)]">{label}</dt>
      <dd
        className={cn(
          "break-words text-[var(--text-primary)] sm:text-right",
          mono && "font-mono text-xs",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
