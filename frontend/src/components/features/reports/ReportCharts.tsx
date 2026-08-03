"use client";

import { SvgChart } from "@/components/features/reports/SvgChart";
import type { ReportChart } from "@/types";

/** Chart grid of a computed report (PART 10 chart panels). */
export function ReportCharts({ charts }: { charts: ReportChart[] }) {
  if (charts.length === 0) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {charts.map((chart) => (
        <section
          key={chart.key}
          aria-label={`Chart: ${chart.title}`}
          className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm"
        >
          <h2 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">{chart.title}</h2>
          <SvgChart chart={chart} />
        </section>
      ))}
    </div>
  );
}
