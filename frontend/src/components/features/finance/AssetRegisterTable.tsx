import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { AssetStatusBadge } from "@/components/features/finance/FinanceBadges";
import { formatMoney, labelFor } from "@/lib/finance/constants";
import { formatDate } from "@/lib/utils";
import type { AssetRegisterRow } from "@/types";

/** ₹ display for a metadata wire string (uses the shared ₹ formatter). */
function moneyOf(raw: string | null | undefined): string {
  if (!raw) return "—";
  const parsed = Number(raw);
  if (Number.isNaN(parsed)) return String(raw);
  return formatMoney(parsed);
}

/**
 * PART 8 asset register — the cross-proposal lens (`GET /finance/assets`).
 * Each row carries its source proposal so the register links back to the
 * procurement workspace.
 */
export function AssetRegisterTable({
  items,
  loading,
}: {
  items: AssetRegisterRow[];
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-4 py-3 font-medium">Asset ID</th>
            <th className="px-4 py-3 font-medium">Item</th>
            <th className="px-4 py-3 font-medium">Category</th>
            <th className="px-4 py-3 font-medium">Serial Number</th>
            <th className="px-4 py-3 font-medium">Location</th>
            <th className="px-4 py-3 font-medium">Assigned To</th>
            <th className="px-4 py-3 font-medium">Warranty</th>
            <th className="px-4 py-3 font-medium">Cost</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Proposal</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={10} />
          ) : (
          items.map((entry, index) => (
            <tr
              key={`${entry.proposal_id}:${entry.row.asset_id ?? index}`}
              className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
            >
              <td className="px-4 py-3 font-mono text-xs">{entry.row.asset_id || "—"}</td>
              <td className="px-4 py-3">{entry.row.item_name || "—"}</td>
              <td className="px-4 py-3">{labelFor(entry.row.category)}</td>
              <td className="px-4 py-3 font-mono text-xs">{entry.row.serial_number || "—"}</td>
              <td className="px-4 py-3">{entry.row.location || "—"}</td>
              <td className="px-4 py-3">{entry.row.assigned_to || "—"}</td>
              <td className="px-4 py-3">
                {entry.row.warranty_expiry ? formatDate(entry.row.warranty_expiry) : "—"}
              </td>
              <td className="px-4 py-3">{moneyOf(entry.row.cost)}</td>
              <td className="px-4 py-3">
                {entry.row.status ? <AssetStatusBadge status={entry.row.status} /> : "—"}
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/finance/${encodeURIComponent(entry.proposal_id)}`}
                  className="text-[var(--accent)] hover:underline"
                >
                  {entry.proposal_number || entry.proposal_title}
                </Link>
              </td>
            </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
