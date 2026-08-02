"use client";

import { ExternalLink, Pencil, Trash2 } from "lucide-react";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import type { AgencyResponse } from "@/types";

/** The funding-agency registry table. */
export function AgencyTable({
  agencies,
  loading = false,
  onEdit,
  onDelete,
}: {
  agencies: AgencyResponse[];
  loading?: boolean;
  onEdit?: (agency: AgencyResponse) => void;
  onDelete?: (agency: AgencyResponse) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[760px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Agency</th>
            <th scope="col" className="px-4 py-3 font-medium">Scheme</th>
            <th scope="col" className="px-4 py-3 font-medium">Contact</th>
            <th scope="col" className="px-4 py-3 font-medium">Website</th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={5} cols={5} />
          ) : (
            agencies.map((agency) => (
              <tr
                key={agency.id}
                className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--text-primary)]">{agency.name}</p>
                  {agency.address ? (
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{agency.address}</p>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {agency.scheme ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {[agency.contact_person, agency.contact_email, agency.contact_phone]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </td>
                <td className="px-4 py-3">
                  {agency.website ? (
                    <a
                      href={agency.website}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-[var(--accent)] hover:underline"
                    >
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Visit
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    {onEdit ? (
                      <button
                        type="button"
                        onClick={() => onEdit(agency)}
                        aria-label={`Edit ${agency.name}`}
                        className="rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--accent)]"
                      >
                        <Pencil className="h-4 w-4" aria-hidden="true" />
                      </button>
                    ) : null}
                    {onDelete ? (
                      <button
                        type="button"
                        onClick={() => onDelete(agency)}
                        aria-label={`Delete ${agency.name}`}
                        className="rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--danger)]"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
