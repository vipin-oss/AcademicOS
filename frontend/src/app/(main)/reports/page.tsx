"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ReportsDashboardCards } from "@/components/features/reports/ReportsDashboardCards";
import { ReportLaunchpad } from "@/components/features/reports/ReportLaunchpad";
import { useReportsDashboard } from "@/hooks/useReportsDashboard";

/**
 * Reports & Analytics hub — the PART 1 dashboard (module totals + budget
 * triplet, computed read over every module) plus the launchpad into each
 * PART 2..10 report workspace.
 */
export default function ReportsPage() {
  const { dashboard, loading, error } = useReportsDashboard();

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs
              items={[
                { label: "Dashboard", href: "/" },
                { label: "Reports & Analytics" },
              ]}
            />
            <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
              Reports & Analytics
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Every number below is computed live from your existing modules —
              nothing is stored twice.
            </p>
          </div>

          <section aria-label="Reports dashboard" aria-busy={loading}>
            {loading ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <CardSkeleton key={i} />
                ))}
              </div>
            ) : error ? (
              <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
                {error}
              </p>
            ) : dashboard ? (
              <ReportsDashboardCards dashboard={dashboard} />
            ) : null}
          </section>

          <section aria-label="Report workspaces" className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Report Workspaces
            </h2>
            <ReportLaunchpad />
          </section>
        </main>
      </div>
    </div>
  );
}
