import type { ReactNode } from "react";
import { CalendarDays, UserRound } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { ObjectResponse } from "@/types";
import { ObjectBadge, TypeBadge, VersionBadge } from "./ObjectBadge";

/**
 * Detail-page header: title, status / type / version badges and the audit
 * summary. Stacks on mobile, actions wrap instead of overflowing.
 */
export function ObjectHeader({
  object,
  actions,
}: {
  object: ObjectResponse;
  actions?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
            {object.title}
          </h1>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <ObjectBadge status={object.status} />
            <TypeBadge type={object.object_type} />
            <VersionBadge version={object.version} />
          </div>

          <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
            <div className="flex items-center gap-1.5">
              <UserRound className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
              <dt className="sr-only">Created by</dt>
              <dd className="break-all">{object.created_by || "—"}</dd>
            </div>
            <div className="flex items-center gap-1.5">
              <CalendarDays className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
              <dt className="sr-only">Created at</dt>
              <dd>{formatDate(object.created_at)}</dd>
            </div>
          </dl>

          <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">{object.id}</p>
        </div>

        {actions ? <div className="flex flex-wrap gap-2 lg:justify-end">{actions}</div> : null}
      </div>
    </div>
  );
}
