"use client";

import { cn } from "@/lib/utils";
import type { DocumentResponse } from "@/types";
import { DocumentRow } from "./DocumentRow";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";

/**
 * Documents table. Columns collapse progressively (sm/md/lg) so the table
 * never scrolls sideways on a phone — the name cell keeps a compact secondary
 * line instead.
 */
export function DocumentTable({
  documents,
  loading = false,
  refreshing = false,
}: {
  documents: DocumentResponse[];
  loading?: boolean;
  /** Background reload: keep rows visible, just dim them slightly. */
  refreshing?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Documents</caption>
          <thead>
            <tr className="text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">
                Document Name
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Linked Object
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                Type
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Size
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Uploaded By
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                Upload Date
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Actions
              </th>
            </tr>
          </thead>
          <tbody
            className={cn(
              "transition-opacity duration-150",
              refreshing && !loading && "opacity-60",
            )}
            aria-busy={loading || refreshing}
          >
            {loading ? (
              <TableSkeleton rows={6} cols={8} />
            ) : (
              documents.map((document) => (
                <DocumentRow key={document.id} document={document} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
