"use client";

import { useState } from "react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { CardSkeleton, DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ExportButtons } from "@/components/features/reports/ExportButtons";
import { ReportCharts } from "@/components/features/reports/ReportCharts";
import { ReportFiltersBar } from "@/components/features/reports/ReportFiltersBar";
import { ReportKpis } from "@/components/features/reports/ReportKpis";
import { ReportTables } from "@/components/features/reports/ReportTables";
import { reportKind } from "@/lib/reports/constants";
import { useReport } from "@/hooks/useReport";
import type { ReportFilters } from "@/types";

/**
 * Report workspace (PART 13) — one shell for every report kind: PART 12
 * filters (only the pickers the kind honours), KPI strip, charts, tables and
 * the PART 11 export buttons. The workspace shows exactly the data the
 * export carries — one computed view, two renderings.
 */
export default function ReportWorkspacePage() {
  const params = useParams<{ kind: string }>();
  const kind = decodeURIComponent(params.kind);
  const meta = reportKind(kind);
  const [filters, setFilters] = useState<ReportFilters>({});
  const { report, loading, error } = useReport(meta ? kind : "", filters);

  if (!meta) notFound();

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-5 p-4 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Breadcrumbs
                items={[
                  { label: "Dashboard", href: "/" },
                  { label: "Reports & Analytics", href: "/reports" },
                  { label: meta.title },
                ]}
              />
              <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
                {report?.title ?? meta.title}
              </h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{meta.description}</p>
            </div>
            <ExportButtons kind={kind} filters={filters} />
          </div>

          {meta.filters.length > 0 ? (
            <ReportFiltersBar kind={kind} filters={filters} onChange={setFilters} />
          ) : null}

          {report && Object.keys(report.applied_filters).length > 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">
              Applied filters:{" "}
              {Object.entries(report.applied_filters)
                .map(([key, value]) => `${key}=${value}`)
                .join(", ")}
              {report.generated_at ? ` · generated ${report.generated_at}` : ""}
            </p>
          ) : null}

          {loading && !report ? (
            <div className="space-y-4" aria-busy="true">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <CardSkeleton key={i} />
                ))}
              </div>
              <DetailSkeleton />
            </div>
          ) : error ? (
            <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          ) : report ? (
            <div className="space-y-6" aria-busy={loading}>
              <ReportKpis kpis={report.kpis} />
              <ReportCharts charts={report.charts} />
              <ReportTables tables={report.tables} />
              {kind === "analytics" ? null : (
                <p className="text-xs text-[var(--text-tertiary)]">
                  Looking for a single record? Open the linked module workspace from any table
                  row — or see the{" "}
                  <Link href="/reports" className="text-[var(--accent)] hover:underline">
                    dashboard
                  </Link>
                  .
                </p>
              )}
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
