"use client";

import { Pencil, Trash2 } from "lucide-react";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { UniversalStatusBadge } from "@/components/features/finance/FinanceBadges";
import { formatMoney } from "@/lib/finance/constants";
import type { VendorResponse } from "@/types";

/** PART 3 vendor registry table with edit/delete actions. */
export function VendorTable({
  vendors,
  loading,
  onEdit,
  onDelete,
}: {
  vendors: VendorResponse[];
  loading: boolean;
  onEdit: (vendor: VendorResponse) => void;
  onDelete: (vendor: VendorResponse) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[880px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-4 py-3 font-medium">Vendor</th>
            <th className="px-4 py-3 font-medium">GST Number</th>
            <th className="px-4 py-3 font-medium">Contact</th>
            <th className="px-4 py-3 font-medium">Proposals</th>
            <th className="px-4 py-3 font-medium">Spent</th>
            <th className="px-4 py-3 font-medium">Lifecycle</th>
            <th className="px-4 py-3 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={5} cols={7} />
          ) : (
          vendors.map((vendor) => (
            <tr
              key={vendor.id}
              className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
            >
              <td className="px-4 py-3">
                <p className="font-medium text-[var(--text-primary)]">{vendor.name}</p>
                {vendor.contact_person ? (
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {vendor.contact_person}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-[var(--text-secondary)]">
                {vendor.gst_number || "—"}
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {vendor.email || vendor.phone || "—"}
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {vendor.stats?.proposals ?? 0}
              </td>
              <td className="px-4 py-3 text-[var(--text-secondary)]">
                {formatMoney(vendor.stats?.spent ?? 0)}
              </td>
              <td className="px-4 py-3">
                <UniversalStatusBadge status={vendor.status} />
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => onEdit(vendor)}
                  aria-label={`Edit "${vendor.name}"`}
                  title="Edit"
                  className="mr-1 inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(vendor)}
                  aria-label={`Delete "${vendor.name}"`}
                  title="Delete"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-1.5 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)]"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </td>
            </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
