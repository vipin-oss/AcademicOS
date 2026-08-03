"use client";

import type { ReportKpi } from "@/types";

/** KPI strip of a computed report (server-formatted value strings). */
export function ReportKpis({ kpis }: { kpis: ReportKpi[] }) {
  if (kpis.length === 0) return null;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3.5 py-3 shadow-sm"
        >
          <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
            {kpi.label}
          </div>
          <p className="mt-1 truncate text-xl font-semibold text-[var(--text-primary)]" title={kpi.value}>
            {kpi.value}
          </p>
        </div>
      ))}
    </div>
  );
}
