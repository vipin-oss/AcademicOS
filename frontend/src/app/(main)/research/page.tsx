"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Filter, Landmark, PiggyBank, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  ProjectModal,
  type ProjectSaveResult,
} from "@/components/features/research/ProjectModal";
import { ProjectTable } from "@/components/features/research/ProjectTable";
import { ResearchDashboardCards } from "@/components/features/research/ResearchDashboardCards";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useProjects } from "@/hooks/useProjects";
import { useResearchDashboard } from "@/hooks/useResearchDashboard";
import { listAgencies } from "@/lib/api/research";
import {
  DEFAULT_PROJECT_PAGE_SIZE,
  PROJECT_LIFECYCLE_STATUSES,
} from "@/lib/research/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { ProjectLifecycleStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The Research hub (PART 10 dashboard + PART 9 projects registry).
 * The dashboard cards and the registry list are independent data sources —
 * each renders its own loading/error state.
 */
export default function ResearchPage() {
  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useResearchDashboard();

  const [search, setSearch] = useState("");
  const [pi, setPi] = useState("");
  const [agency, setAgency] = useState("");
  const [status, setStatus] = useState<ProjectLifecycleStatus | "all">("all");
  const [yearText, setYearText] = useState("");
  const [department, setDepartment] = useState("");
  const [agencyNames, setAgencyNames] = useState<string[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

  const year =
    yearText.trim() && /^\d{4}$/.test(yearText.trim()) ? Number(yearText.trim()) : null;

  const {
    items,
    total,
    page,
    pageSize,
    loading,
    refreshing,
    error,
    isSearching,
    searchActive,
    filterActive,
    setPage,
    refresh,
  } = useProjects({
    pageSize: DEFAULT_PROJECT_PAGE_SIZE,
    search,
    pi: pi.trim() || null,
    agency: agency || null,
    status: status === "all" ? null : status,
    year,
    department: department.trim() || null,
  });

  // Pick up a message handed over by another page (e.g. "project deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  // The agency filter is a choice of registered agencies (the backend matches
  // linked agency names) — load the registry once for the select.
  useEffect(() => {
    const controller = new AbortController();
    listAgencies({ pageSize: 100 }, { signal: controller.signal })
      .then((response) => setAgencyNames(response.items.map((item) => item.name)))
      .catch(() => setAgencyNames([]));
    return () => controller.abort();
  }, []);

  const handleSaved = useCallback(
    (result: ProjectSaveResult) => {
      setModalOpen(false);
      refresh();
      refreshDashboard();
      show(
        "success",
        `“${result.project.title}” ${result.mode === "edit" ? "updated" : "registered"} successfully.`,
      );
    },
    [refresh, refreshDashboard, show],
  );

  const handleRefresh = useCallback(() => {
    refresh();
    refreshDashboard();
  }, [refresh, refreshDashboard]);

  const showTable = loading || items.length > 0;
  const filtering = searchActive || filterActive;

  const clearFilters = () => {
    setSearch("");
    setPi("");
    setAgency("");
    setStatus("all");
    setYearText("");
    setDepartment("");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Research" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Research Projects &amp; Grants</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} project${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search title, code, keywords…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={loading || refreshing || dashboardLoading}
                  aria-label="Refresh research"
                  title="Refresh"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                    aria-hidden="true"
                  />
                </button>
                <Link
                  href="/research/agencies"
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <Landmark className="h-4 w-4" aria-hidden="true" /> Agencies
                </Link>
                <Link
                  href="/research/grants"
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <PiggyBank className="h-4 w-4" aria-hidden="true" /> Grants
                </Link>
                <button
                  type="button"
                  onClick={() => setModalOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Project
                </button>
              </div>
            </div>
          </div>

          {/* PART 10 dashboard */}
          <div className="mt-6">
            {dashboardError ? (
              <p
                role="alert"
                className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                Could not load the research dashboard — {dashboardError}
              </p>
            ) : dashboardLoading || !dashboard ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
                {Array.from({ length: 6 }, (_, index) => (
                  <CardSkeleton key={index} lines={2} />
                ))}
              </div>
            ) : (
              <ResearchDashboardCards dashboard={dashboard} />
            )}
          </div>

          {/* PART 9 filters */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <input
              type="text"
              value={pi}
              onChange={(event) => setPi(event.target.value)}
              placeholder="PI / team member"
              aria-label="Filter by PI"
              className={`${INPUT_CLASS} w-40`}
            />
            <select
              value={agency}
              onChange={(event) => setAgency(event.target.value)}
              aria-label="Filter by agency"
              className={SELECT_CLASS}
            >
              <option value="">All agencies</option>
              {agencyNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as ProjectLifecycleStatus | "all")
              }
              aria-label="Filter by lifecycle status"
              className={SELECT_CLASS}
            >
              <option value="all">All lifecycle states</option>
              {PROJECT_LIFECYCLE_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              inputMode="numeric"
              value={yearText}
              onChange={(event) => setYearText(event.target.value)}
              placeholder="Year"
              aria-label="Filter by year"
              className={`${INPUT_CLASS} w-24`}
            />
            <input
              type="text"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              placeholder="Department"
              aria-label="Filter by department"
              className={`${INPUT_CLASS} w-40`}
            />
          </div>

          {/* Projects registry */}
          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load projects"
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
            ) : showTable ? (
              <>
                <ProjectTable projects={items} loading={loading} />
                {!loading ? (
                  <Pagination
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    disabled={refreshing}
                  />
                ) : null}
              </>
            ) : filtering ? (
              <EmptyState
                title="No matching projects"
                description="Nothing matches your search and filters. Try different terms or clear them."
                action={
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    Clear filters
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="No research projects yet"
                description="Register your first project — link the PI and team, attach funding agencies and track the lifecycle from draft to closed."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Project
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <ProjectModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
