"use client";

import { CommitteeStatusBadge, CommitteeTypeBadge } from "./CommitteeBadges";
import { committeeTypeLabel } from "@/lib/committees/constants";
import { formatDate } from "@/lib/utils";
import type { CommitteeResponse } from "@/types";

/** Compact committee identity header for the workspace page (with action slot). */
export function CommitteeHeader({
  committee,
  actions,
}: {
  committee: CommitteeResponse;
  actions?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{committee.name}</h2>
            {committee.committee_type ? (
              <CommitteeTypeBadge type={committee.committee_type} />
            ) : null}
            <CommitteeStatusBadge status={committee.status} />
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {[
              committee.committee_code,
              committee.committee_type
                ? `${committeeTypeLabel(committee.committee_type)} committee`
                : null,
              committee.department,
              committee.school,
            ]
              .filter(Boolean)
              .join(" · ") || " "}
          </p>
          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
            {[
              committee.constitution_date
                ? `Constituted ${formatDate(committee.constitution_date)}`
                : null,
              committee.expiry_date ? `expires ${formatDate(committee.expiry_date)}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {committee.tags.length > 0 ? (
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              {committee.tags.map((tag) => `#${tag}`).join(" ")}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
      {committee.description ? (
        <p className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-sm text-[var(--text-secondary)]">
          <span className="font-medium text-[var(--text-primary)]">Description: </span>
          {committee.description}
        </p>
      ) : null}
    </div>
  );
}
