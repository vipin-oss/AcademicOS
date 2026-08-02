"use client";

import { useCallback, useEffect } from "react";
import { useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  ClassModal,
  type ClassSaveResult,
} from "@/components/features/teaching/ClassModal";
import { ClassTable } from "@/components/features/teaching/ClassTable";
import { DashboardCards } from "@/components/features/teaching/DashboardCards";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useTeachingDashboard } from "@/hooks/useTeachingDashboard";
import { consumeFlash } from "@/lib/objects/flash";

export default function TeachingPage() {
  const { dashboard, loading, error, refresh } = useTeachingDashboard();
  const [modalOpen, setModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { toast, show, dismiss } = useToast();

  // Pick up a message handed over by another page (e.g. "class deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    refresh();
  }, [refresh]);

  // Clear the local spinner once the reload lands.
  useEffect(() => {
    if (!loading) setRefreshing(false);
  }, [loading]);

  const handleSaved = useCallback(
    (result: ClassSaveResult) => {
      setModalOpen(false);
      refresh();
      show(
        "success",
        `“${result.cls.title}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
      );
    },
    [refresh, show],
  );

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Teaching" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Teaching</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : `${dashboard?.class_count ?? 0} class${(dashboard?.class_count ?? 0) === 1 ? "" : "es"} this term`}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleRefresh}
                disabled={loading || refreshing}
                aria-label="Refresh teaching dashboard"
                title="Refresh"
                className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
              </button>
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
              >
                <Plus className="h-4 w-4" aria-hidden="true" /> Create Class
              </button>
            </div>
          </div>

          <div className="mt-6 space-y-6">
            {error ? (
              <EmptyState
                title="Could not load the teaching dashboard"
                description={error}
                action={
                  <button
                    type="button"
                    onClick={handleRefresh}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
                  </button>
                }
              />
            ) : loading ? (
              <DetailSkeleton />
            ) : dashboard ? (
              <>
                <DashboardCards dashboard={dashboard} />

                <section aria-label="Classes">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold text-[var(--text-primary)]">Classes</h2>
                    <p className="text-xs text-[var(--text-tertiary)]">
                      Every class is a reusable academic object.
                    </p>
                  </div>
                  {dashboard.classes.length === 0 ? (
                    <EmptyState
                      title="No classes yet"
                      description="Create your first class — enroll students, add assignments, record attendance and compute the gradebook in one workspace."
                      action={
                        <button
                          type="button"
                          onClick={() => setModalOpen(true)}
                          className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                        >
                          <Plus className="h-4 w-4" aria-hidden="true" /> Create Class
                        </button>
                      }
                    />
                  ) : (
                    <ClassTable classes={dashboard.classes} />
                  )}
                </section>
              </>
            ) : null}
          </div>
        </main>
      </div>

      <ClassModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
