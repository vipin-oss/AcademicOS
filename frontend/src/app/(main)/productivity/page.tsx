"use client";

/**
 * Productivity Hub — the personal productivity center: what needs attention
 * today, what is due soon, what is overdue, what is coming next. Tabs:
 * Overview (PART 6 dashboard cards + PART 5 reminders), Calendar (PART 1/2),
 * Tasks (PART 3), Notifications (PART 4), Search (PART 7).
 */
import { useState } from "react";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ProductivityDashboardCards } from "@/components/features/productivity/ProductivityDashboardCards";
import { ReminderPanel } from "@/components/features/productivity/ReminderPanel";
import { CalendarWorkspace } from "@/components/features/productivity/CalendarWorkspace";
import { TasksPanel } from "@/components/features/productivity/TasksPanel";
import { SearchPanel } from "@/components/features/productivity/SearchPanel";
import { NotificationsCenter } from "@/components/features/notifications/NotificationsCenter";
import { useProductivityDashboard } from "@/hooks/useProductivity";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "calendar", label: "Calendar" },
  { id: "tasks", label: "Tasks" },
  { id: "notifications", label: "Notifications" },
  { id: "search", label: "Search" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function OverviewTab() {
  const { dashboard, loading, error } = useProductivityDashboard();
  return (
    <div className="space-y-6">
      <section aria-label="Productivity dashboard" aria-busy={loading}>
        {loading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <CardSkeleton key={index} />
            ))}
          </div>
        ) : error ? (
          <p
            role="alert"
            className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
          >
            {error}
          </p>
        ) : dashboard ? (
          <ProductivityDashboardCards dashboard={dashboard} />
        ) : null}
      </section>
      <ReminderPanel />
    </div>
  );
}

export default function ProductivityPage() {
  const [tab, setTab] = useState<TabId>("overview");

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs
              items={[{ label: "Dashboard", href: "/" }, { label: "Productivity" }]}
            />
            <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
              Productivity Hub
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Your day at a glance — what needs attention today, what is due soon, what is
              overdue, and what is coming next across every module.
            </p>
          </div>

          <div
            role="tablist"
            aria-label="Productivity sections"
            className="flex flex-wrap gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-1"
          >
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                aria-controls={`productivity-panel-${item.id}`}
                id={`productivity-tab-${item.id}`}
                onClick={() => setTab(item.id)}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${
                  tab === item.id
                    ? "bg-[var(--accent)] text-white"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            id={`productivity-panel-${tab}`}
            aria-labelledby={`productivity-tab-${tab}`}
          >
            {tab === "overview" ? <OverviewTab /> : null}
            {tab === "calendar" ? <CalendarWorkspace /> : null}
            {tab === "tasks" ? <TasksPanel /> : null}
            {tab === "notifications" ? <NotificationsCenter /> : null}
            {tab === "search" ? <SearchPanel /> : null}
          </div>
        </main>
      </div>
    </div>
  );
}
