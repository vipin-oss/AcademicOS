"use client";

import { cn } from "@/lib/utils";
import type { ObjectResponse } from "@/types";
import { ObjectRow } from "./ObjectRow";
import { TableSkeleton } from "./LoadingSkeleton";

/**
 * Objects table. Columns collapse progressively (sm/md/lg) so the table never
 * scrolls sideways on a phone — the row keeps a compact secondary line instead.
 */
export function ObjectTable({
  objects,
  loading = false,
  refreshing = false,
}: {
  objects: ObjectResponse[];
  loading?: boolean;
  /** Background reload: keep rows visible, just dim them slightly. */
  refreshing?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Objects</caption>
          <thead>
            <tr className="text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">
                Title
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                Type
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                Created By
              </th>
              <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                Created At
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
              <TableSkeleton rows={6} cols={5} />
            ) : (
              objects.map((object) => <ObjectRow key={object.id} object={object} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
