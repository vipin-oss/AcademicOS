import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  PriorityBadge,
  ProposalStatusBadge,
} from "@/components/features/finance/FinanceBadges";
import { formatMoney } from "@/lib/finance/constants";
import { formatDate } from "@/lib/utils";
import type { ProposalResponse } from "@/types";

function primaryVendor(proposal: ProposalResponse): string {
  const recommended = proposal.comparative.find((row) => row.recommended);
  if (recommended?.vendor_name) return recommended.vendor_name;
  const first = [...proposal.purchase_orders, ...proposal.quotations, ...proposal.bills].find(
    (row) => row.vendor_name,
  );
  return first?.vendor_name ?? "—";
}

/** PART 1 directory table (number/title/vendor/dept/status/priority/cost/date). */
export function ProposalTable({
  proposals,
  loading,
}: {
  proposals: ProposalResponse[];
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-4 py-3 font-medium">Proposal</th>
            <th className="px-4 py-3 font-medium">Vendor</th>
            <th className="px-4 py-3 font-medium">Department</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Priority</th>
            <th className="px-4 py-3 font-medium">Est. Cost</th>
            <th className="px-4 py-3 font-medium">Date</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={5} cols={7} />
          ) : (
          proposals.map((proposal) => (
            <tr
              key={proposal.id}
              className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/finance/${encodeURIComponent(proposal.id)}`}
                  className="font-medium text-[var(--accent)] hover:underline"
                >
                  {proposal.title}
                </Link>
                <p className="mt-0.5 font-mono text-xs text-[var(--text-tertiary)]">
                  {proposal.proposal_number || "—"}
                </p>
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">{primaryVendor(proposal)}</td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {proposal.department || "—"}
              </td>
              <td className="px-4 py-3">
                <ProposalStatusBadge status={proposal.proposal_status} />
              </td>
              <td className="px-4 py-3">
                {proposal.priority ? <PriorityBadge priority={proposal.priority} /> : "—"}
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {formatMoney(proposal.estimated_cost)}
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {formatDate(proposal.proposal_date)}
              </td>
            </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

