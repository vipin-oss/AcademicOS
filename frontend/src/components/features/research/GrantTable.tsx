"use client";

import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { formatAmount } from "@/lib/research/constants";
import type { GrantResponse } from "@/types";

/** The grants registry table (mirrors StudentTable structure). */
export function GrantTable({
  grants,
  loading = false,
}: {
  grants: GrantResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[860px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Grant</th>
            <th scope="col" className="px-4 py-3 font-medium">Agency</th>
            <th scope="col" className="px-4 py-3 font-medium">Project(s)</th>
            <th scope="col" className="px-4 py-3 font-medium">Sanctioned</th>
            <th scope="col" className="px-4 py-3 font-medium">Released</th>
            <th scope="col" className="px-4 py-3 font-medium">Utilized</th>
            <th scope="col" className="px-4 py-3 font-medium">Remaining</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={7} />
          ) : (
            grants.map((grant) => (
              <tr
                key={grant.id}
                className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/research/grants/${encodeURIComponent(grant.id)}`}
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {grant.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{grant.grant_number}</p>
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {(grant.links?.funding_agencies ?? []).map((a) => a.title).join(", ") || "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {(grant.links?.projects ?? []).map((p) => p.title).join(", ") || "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatAmount(grant.budget?.approved ?? grant.amount)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatAmount(grant.budget?.released)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatAmount(grant.budget?.utilized)}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                  {formatAmount(grant.budget?.remaining)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
