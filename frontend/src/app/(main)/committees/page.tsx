"use client";

import { useCallback, useEffect, useState } from "react";
import { Filter, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  CommitteeModal,
  type CommitteeSaveResult,
} from "@/components/features/committees/CommitteeModal";
import { CommitteeTable } from "@/components/features/committees/CommitteeTable";
import { CommitteesDashboardCards } from "@/components/features/committees/CommitteesDashboardCards";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useCommittees } from "@/hooks/useCommittees";
import { useCommitteesDashboard } from "@/hooks/useCommitteesDashboard";
import {
  COMMITTEE_STATUS_OPTIONS,
  COMMITTEE_TYPES,
  DEFAULT_COMMITTEE_PAGE_SIZE,
} from "@/lib/committees/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { ResearchObjectStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The Committees hub (PART 8 dashboard + PART 9 registry with search/filters).
 * The dashboard cards and the registry list are independent data sources —
 * each renders its own loading/error state.
 */
export default function CommitteesPage() {
  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useCommitteesDashboard();

  const [search, setSearch] = useState("");
  const [committeeType, setCommitteeType] = useState("");
  const [department, setDepartment] = useState("");
  const [chairperson, setChairperson] = useState("");
  const [status, setStatus] = useState<ResearchObjectStatus | "all">("all");
  const [yearText, setYearText] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

  const meetingYear =
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
  } = useCommittees({
    pageSize: DEFAULT_COMMITTEE_PAGE_SIZE,
    search,
    committeeType: committeeType || null,
    department: department.trim() || null,
    chairperson: chairperson.trim() || null,
    status: status === "all" ? null : status,
    meetingYear,
  });

  // Pick up a message handed over by another page (e.g. "committee deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: CommitteeSaveResult) => {
      setModalOpen(false);
      refresh();
      refreshDashboard();
      show(
        "success",
        `“${result.committee.name}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
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
    setCommitteeType("");
    setDepartment("");
    setChairperson("");
    setStatus("all");
    setYearText("");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Committees" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Committees &amp; Meetings</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} committee${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search name, code, members…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={loading || refreshing || dashboardLoading}
                  aria-label="Refresh committees"
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
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Committee
                </button>
              </div>
            </div>
          </div>

          {/* PART 8 dashboard */}
          <div className="mt-6">
            {dashboardError ? (
              <p
                role="alert"
                className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                Could not load the committees dashboard — {dashboardError}
              </p>
            ) : dashboardLoading || !dashboard ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
                {Array.from({ length: 6 }, (_, index) => (
                  <CardSkeleton key={index} lines={2} />
                ))}
              </div>
            ) : (
              <CommitteesDashboardCards dashboard={dashboard} />
            )}
          </div>

          {/* PART 9 filters */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={committeeType}
              onChange={(event) => setCommitteeType(event.target.value)}
              aria-label="Filter by committee type"
              className={SELECT_CLASS}
            >
              <option value="">All types</option>
              {COMMITTEE_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              placeholder="Department"
              aria-label="Filter by department"
              className={`${INPUT_CLASS} w-40`}
            />
            <input
              type="text"
              value={chairperson}
              onChange={(event) => setChairperson(event.target.value)}
              placeholder="Chairperson / convener"
              aria-label="Filter by chairperson"
              className={`${INPUT_CLASS} w-44`}
            />
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as ResearchObjectStatus | "all")
              }
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              {COMMITTEE_STATUS_OPTIONS.map((option) => (
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
              placeholder="Meeting year"
              aria-label="Filter by meeting year"
              className={`${INPUT_CLASS} w-32`}
            />
          </div>

          {/* Committees registry */}
          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load committees"
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
                <CommitteeTable committees={items} loading={loading} />
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
                title="No matching committees"
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
                title="No committees yet"
                description="Create your first committee — add members, schedule meetings and track agendas, minutes and action items."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Committee
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <CommitteeModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
