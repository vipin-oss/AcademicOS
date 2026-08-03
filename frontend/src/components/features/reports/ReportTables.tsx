"use client";

import Link from "next/link";
import type { ReportTable } from "@/types";

/** Renders every table of a computed report — strings cells, optional
 * per-cell module links (export ignores these by design). */
export function ReportTables({ tables }: { tables: ReportTable[] }) {
  return (
    <div className="space-y-6">
      {tables.map((table) => (
        <section
          key={table.key}
          aria-label={table.title}
          className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm"
        >
          <h2 className="border-b border-[var(--border-subtle)] px-4 py-2.5 text-sm font-semibold text-[var(--text-primary)]">
            {table.title}
            <span className="ml-2 text-xs font-normal text-[var(--text-tertiary)]">
              ({table.rows.length} {table.rows.length === 1 ? "row" : "rows"})
            </span>
          </h2>
          {table.rows.length === 0 ? (
            <p className="px-4 py-4 text-sm text-[var(--text-tertiary)]">
              Nothing matches the current filters.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-max border-collapse text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-app)]">
                    {table.columns.map((column) => (
                      <th
                        key={column}
                        scope="col"
                        className="whitespace-nowrap px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr
                      key={rowIndex}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
                    >
                      {row.map((cell, cellIndex) => {
                        const href = table.hrefs?.[rowIndex]?.[cellIndex];
                        return (
                          <td
                            key={cellIndex}
                            className="whitespace-nowrap px-4 py-2 text-[var(--text-secondary)]"
                          >
                            {href ? (
                              <Link href={href} className="text-[var(--accent)] hover:underline">
                                {cell}
                              </Link>
                            ) : (
                              cell
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
