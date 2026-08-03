"use client";

import { Download } from "lucide-react";
import { exportUrl } from "@/lib/api/reports";
import { EXPORT_FORMATS } from "@/lib/reports/constants";
import type { ReportFilters } from "@/types";

/** PART 11 export buttons — plain links to the GET export endpoints
 * (CSV / XLSX / PDF generated server-side from the same computed view). */
export function ExportButtons({ kind, filters }: { kind: string; filters: ReportFilters }) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label="Export report">
      {EXPORT_FORMATS.map((format) => (
        <a
          key={format.key}
          href={exportUrl(kind, format.key, filters)}
          download
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" />
          {format.label}
        </a>
      ))}
    </div>
  );
}
