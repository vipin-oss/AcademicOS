"use client";

import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { committeeRoleLabel, committeeTypeLabel } from "@/lib/committees/constants";
import { formatDate } from "@/lib/utils";
import { CommitteeStatusBadge } from "./CommitteeBadges";
import type { CommitteeResponse } from "@/types";

/** Leadership roles shown in the "leadership" column (chairperson first). */
const LEADERSHIP_RANK: Record<string, number> = { chairperson: 0, convener: 1, coordinator: 2 };

function LeadershipLine({ committee }: { committee: CommitteeResponse }) {
  const leaders = (committee.members ?? [])
    .filter((member) => member.role in LEADERSHIP_RANK)
    .sort((a, b) => LEADERSHIP_RANK[a.role] - LEADERSHIP_RANK[b.role]);
  if (leaders.length === 0) return null;
  return (
    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
      {leaders.map((member) => `${member.name} (${committeeRoleLabel(member.role)})`).join(", ")}
    </p>
  );
}

/** The committees registry table (mirrors ProjectTable structure). */
export function CommitteeTable({
  committees,
  loading = false,
}: {
  committees: CommitteeResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[860px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Committee</th>
            <th scope="col" className="px-4 py-3 font-medium">Type</th>
            <th scope="col" className="px-4 py-3 font-medium">Department</th>
            <th scope="col" className="px-4 py-3 font-medium">Constituted</th>
            <th scope="col" className="px-4 py-3 font-medium">Members</th>
            <th scope="col" className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={6} />
          ) : (
            committees.map((committee) => (
              <tr
                key={committee.id}
                className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/committees/${encodeURIComponent(committee.id)}`}
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {committee.name}
                  </Link>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {committee.committee_code ?? "No code"}
                  </p>
                  <LeadershipLine committee={committee} />
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {committeeTypeLabel(committee.committee_type)}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {committee.department ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {formatDate(committee.constitution_date)}
                  {committee.expiry_date ? ` → ${formatDate(committee.expiry_date)}` : ""}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {(committee.members ?? []).length || "—"}
                </td>
                <td className="px-4 py-3">
                  <CommitteeStatusBadge status={committee.status} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
