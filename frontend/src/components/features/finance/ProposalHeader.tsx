import { Building2, CalendarDays, User2 } from "lucide-react";
import {
  PriorityBadge,
  ProposalStatusBadge,
  UniversalStatusBadge,
} from "@/components/features/finance/FinanceBadges";
import { formatDate } from "@/lib/utils";
import type { ProposalResponse } from "@/types";

/** Workspace identity header (PART 1 core fields + badges). */
export function ProposalHeader({ proposal }: { proposal: ProposalResponse }) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{proposal.title}</h1>
          <p className="mt-1 font-mono text-xs text-[var(--text-tertiary)]">
            {proposal.proposal_number || "No proposal number"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ProposalStatusBadge status={proposal.proposal_status} />
          {proposal.priority ? <PriorityBadge priority={proposal.priority} /> : null}
          <UniversalStatusBadge status={proposal.status} />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-[var(--text-secondary)]">
        {proposal.department ? (
          <span className="inline-flex items-center gap-1.5">
            <Building2 className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {proposal.department}
          </span>
        ) : null}
        {proposal.proposal_date ? (
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {formatDate(proposal.proposal_date)}
          </span>
        ) : null}
        {proposal.requested_name ? (
          <span className="inline-flex items-center gap-1.5">
            <User2 className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            Requested by {proposal.requested_name}
          </span>
        ) : null}
      </div>
    </div>
  );
}
