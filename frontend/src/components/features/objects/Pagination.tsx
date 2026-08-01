"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Windowed page list: 1 … 4 [5] 6 … 12 */
function pageItems(page: number, totalPages: number): (number | "gap")[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);

  const items: (number | "gap")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);

  if (start > 2) items.push("gap");
  for (let i = start; i <= end; i += 1) items.push(i);
  if (end < totalPages - 1) items.push("gap");
  items.push(totalPages);

  return items;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  disabled = false,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  const canPrev = page > 1 && !disabled;
  const canNext = page < totalPages && !disabled;

  const navButton =
    "inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-col items-center justify-between gap-3 sm:flex-row"
    >
      <p className="text-sm text-[var(--text-tertiary)]">
        Showing <span className="font-medium text-[var(--text-secondary)]">{first}</span>–
        <span className="font-medium text-[var(--text-secondary)]">{last}</span> of{" "}
        <span className="font-medium text-[var(--text-secondary)]">{total}</span>
      </p>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!canPrev}
          className={navButton}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Previous</span>
        </button>

        <ul className="hidden items-center gap-1 sm:flex">
          {pageItems(page, totalPages).map((item, index) =>
            item === "gap" ? (
              <li
                key={`gap-${index}`}
                className="px-1.5 text-sm text-[var(--text-tertiary)]"
                aria-hidden="true"
              >
                …
              </li>
            ) : (
              <li key={item}>
                <button
                  type="button"
                  onClick={() => onPageChange(item)}
                  disabled={disabled}
                  aria-current={item === page ? "page" : undefined}
                  aria-label={`Page ${item}`}
                  className={cn(
                    "min-w-[2rem] rounded-lg px-2.5 py-1.5 text-sm transition-colors disabled:cursor-not-allowed",
                    item === page
                      ? "bg-[var(--accent)] font-medium text-white"
                      : "border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]",
                  )}
                >
                  {item}
                </button>
              </li>
            ),
          )}
        </ul>

        <span className="text-sm text-[var(--text-tertiary)] sm:hidden">
          {page} / {totalPages}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!canNext}
          className={navButton}
          aria-label="Next page"
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
