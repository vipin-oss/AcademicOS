import { cn } from "@/lib/utils";

/** A single shimmering bar. */
export function SkeletonLine({ className }: { className?: string }) {
  return (
    <div
      className={cn("h-4 w-full animate-pulse rounded bg-[var(--bg-hover)]", className)}
      aria-hidden="true"
    />
  );
}

/** Table body placeholder. Column count must match the visible header. */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  const columnVisibility = ["", "hidden sm:table-cell", "", "hidden md:table-cell", "hidden lg:table-cell"];
  return (
    <>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <tr key={rowIndex} className="border-t border-[var(--border-subtle)]">
          {Array.from({ length: cols }).map((__, colIndex) => (
            <td key={colIndex} className={cn("px-4 py-3", columnVisibility[colIndex] ?? "")}>
              <SkeletonLine className="max-w-[160px]" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/**
 * Backwards-compatible alias — `LoadingSkeleton` was the original export and is
 * still used for table bodies.
 */
export function LoadingSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return <TableSkeleton rows={rows} cols={cols} />;
}

/** Card/section placeholder used by the detail page. */
export function CardSkeleton({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-sm",
        className,
      )}
    >
      <SkeletonLine className="mb-4 h-3 w-24" />
      <div className="space-y-3">
        {Array.from({ length: lines }).map((_, index) => (
          <SkeletonLine key={index} className={index % 2 === 0 ? "w-full" : "w-2/3"} />
        ))}
      </div>
    </div>
  );
}

/** Full detail-page placeholder: header + two columns of cards. */
export function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-sm">
        <SkeletonLine className="h-6 w-2/3 max-w-sm" />
        <div className="mt-4 flex gap-2">
          <SkeletonLine className="h-5 w-20 rounded-full" />
          <SkeletonLine className="h-5 w-24 rounded-full" />
          <SkeletonLine className="h-5 w-12 rounded-full" />
        </div>
        <SkeletonLine className="mt-4 h-3 w-1/2 max-w-xs" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CardSkeleton lines={4} />
        <CardSkeleton lines={4} />
        <CardSkeleton lines={3} />
        <CardSkeleton lines={3} />
      </div>
    </div>
  );
}
