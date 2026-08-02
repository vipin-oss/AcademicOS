"use client";

import { ResearchStatusBadge } from "./ResearchBadges";
import { formatAmount } from "@/lib/research/constants";
import { utilizationRatio } from "@/lib/research/constants";
import type { GrantResponse } from "@/types";

/** Grant workspace header: identity, agency, sanctioned amount + budget bar. */
export function GrantHeader({
  grant,
  actions,
}: {
  grant: GrantResponse;
  actions?: React.ReactNode;
}) {
  const ratio = utilizationRatio(grant.budget?.utilized ?? null, grant.budget?.approved ?? null);
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{grant.title}</h2>
            <ResearchStatusBadge status={grant.status} />
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {[
              grant.grant_number,
              (grant.links?.funding_agencies ?? []).map((a) => a.title).join(", ") || null,
              grant.release_schedule ? `Schedule: ${grant.release_schedule}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-[var(--border-subtle)] pt-3 sm:grid-cols-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Sanctioned</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
            {formatAmount(grant.budget?.approved ?? grant.amount)}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Released</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
            {formatAmount(grant.budget?.released)}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Utilized</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
            {formatAmount(grant.budget?.utilized)}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Remaining</p>
          <p className="mt-1 text-lg font-semibold text-[var(--text-primary)]">
            {formatAmount(grant.budget?.remaining)}
          </p>
        </div>
      </div>
      {ratio != null ? (
        <div
          className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(ratio * 100)}
          aria-label="Grant utilization"
        >
          <div
            className="h-full rounded-full bg-[var(--warning)] transition-all"
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
