"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarPlus, Filter, Plus, RefreshCw, Download } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  EventModal,
  type EventSaveResult,
} from "@/components/features/events/EventModal";
import { EventTable } from "@/components/features/events/EventTable";
import { EventsDashboardCards } from "@/components/features/events/EventsDashboardCards";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useEvents } from "@/hooks/useEvents";
import { useEventsDashboard } from "@/hooks/useEventsDashboard";
import {
  DEFAULT_EVENT_PAGE_SIZE,
  EVENT_STATUSES,
  EVENT_TYPES,
  PARTICIPATION_ROLES,
  yearOptions,
} from "@/lib/events/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type {
  EventStatus,
  EventType,
  ParticipationRole,
} from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The Events & Academic Activities hub (PART 9 dashboard + PART 1 registry
 * with PART 10 search/filters). The dashboard and the registry list are
 * independent data sources — each renders its own loading/error state (same
 * split as the Finance hub).
 */
export default function EventsPage() {
  const {
    dashboard,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useEventsDashboard();

  const [search, setSearch] = useState("");
  const [eventType, setEventType] = useState<EventType | "all">("all");
  const [year, setYear] = useState("");
  const [role, setRole] = useState<ParticipationRole | "all">("all");
  const [department, setDepartment] = useState("");
  const [organizer, setOrganizer] = useState("");
  const [status, setStatus] = useState<EventStatus | "all">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

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
  } = useEvents({
    pageSize: DEFAULT_EVENT_PAGE_SIZE,
    search,
    eventType: eventType === "all" ? null : eventType,
    year: year || null,
    role: role === "all" ? null : role,
    department: department.trim() || null,
    organizer: organizer.trim() || null,
    status: status === "all" ? null : status,
  });

  // Pick up a message handed over by another page (e.g. "event deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: EventSaveResult) => {
      setModalOpen(false);
      refresh();
      refreshDashboard();
      show(
        "success",
        `“${result.event.title}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
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
    setEventType("all");
    setYear("");
    setRole("all");
    setDepartment("");
    setOrganizer("");
    setStatus("all");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Events" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Events &amp; Academic Activities</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} event${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search title, code, organizer…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={loading || refreshing || dashboardLoading}
                  aria-label="Refresh events"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Event
                </button>
                <a
                  href="/api/v1/events/export"
                  download
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  title="Export events as CSV"
                >
                  <Download className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>

          {/* PART 9 dashboard */}
          <div className="mt-6">
            {dashboardError ? (
              <p
                role="alert"
                className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                Could not load the events dashboard — {dashboardError}
              </p>
            ) : dashboardLoading || !dashboard ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
                {Array.from({ length: 7 }, (_, index) => (
                  <CardSkeleton key={index} lines={2} />
                ))}
              </div>
            ) : (
              <EventsDashboardCards dashboard={dashboard} />
            )}
          </div>

          {/* PART 10 filters */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={eventType}
              onChange={(change) => setEventType(change.target.value as EventType | "all")}
              aria-label="Filter by event type"
              className={SELECT_CLASS}
            >
              <option value="all">All types</option>
              {EVENT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={year}
              onChange={(change) => setYear(change.target.value)}
              aria-label="Filter by year"
              className={SELECT_CLASS}
            >
              <option value="">All years</option>
              {yearOptions().map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={role}
              onChange={(change) => setRole(change.target.value as ParticipationRole | "all")}
              aria-label="Filter by role"
              className={SELECT_CLASS}
            >
              <option value="all">All roles</option>
              {PARTICIPATION_ROLES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={department}
              onChange={(change) => setDepartment(change.target.value)}
              placeholder="Department"
              aria-label="Filter by department"
              className={`${INPUT_CLASS} w-36`}
            />
            <input
              type="text"
              value={organizer}
              onChange={(change) => setOrganizer(change.target.value)}
              placeholder="Organizer"
              aria-label="Filter by organizer"
              className={`${INPUT_CLASS} w-36`}
            />
            <select
              value={status}
              onChange={(change) => setStatus(change.target.value as EventStatus | "all")}
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              <option value="all">All statuses</option>
              {EVENT_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* PART 1 registry */}
          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load events"
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
                <EventTable events={items} loading={loading} />
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
                title="No matching events"
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
                title="No events yet"
                description="Register your first event — conferences, FDPs, invited talks, colloquia — then track participation, speakers, schedule and certificates."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <CalendarPlus className="h-4 w-4" aria-hidden="true" /> New Event
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <EventModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
