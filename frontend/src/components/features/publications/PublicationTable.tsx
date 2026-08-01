"use client";

import { cn } from "@/lib/utils";
import type { PublicationResponse } from "@/types";
import { PublicationRow } from "./PublicationRow";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";

/**
 * Publications table. Columns collapse progressively (sm/md/lg) so the table
 * never scrolls sideways on a phone — the title cell keeps a compact
 * secondary line instead. (Mirrors the Documents table.)
 */
export function PublicationTable({
  publications,
  loading = false,
  refreshing = false,
}: {
  publications: PublicationResponse[];
  loading?: boolean;
  /** Background reload: keep rows visible, just dim them slightly. */
  refreshing?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Publications</caption>
          <thead>
            <tr className="text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">
                Publication
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                Type
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Venue
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                Year
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                Quartile
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                Pipeline
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
              publications.map((publication) => (
                <PublicationRow key={publication.id} publication={publication} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
