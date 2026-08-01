import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface)] px-6 py-12 text-center">
      <p className="text-base font-medium text-[var(--text-primary)]">{title}</p>
      {description && <p className="max-w-sm text-sm text-[var(--text-tertiary)]">{description}</p>}
      {action}
    </div>
  );
}
