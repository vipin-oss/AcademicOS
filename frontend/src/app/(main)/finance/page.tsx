"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Filter, Package, Plus, RefreshCw, Truck } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  ProposalModal,
  type ProposalSaveResult,
} from "@/components/features/finance/ProposalModal";
import { ProposalTable } from "@/components/features/finance/ProposalTable";
import { FinanceDashboardCards } from "@/components/features/finance/FinanceDashboardCards";
import { BudgetTrackingPanel } from "@/components/features/finance/BudgetTrackingPanel";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useProposals } from "@/hooks/useProposals";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";
import {
  DEFAULT_PROPOSAL_PAGE_SIZE,
  PROPOSAL_STATUSES,
  financialYearOptions,
} from "@/lib/finance/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { ProposalStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The Finance & Procurement hub (PART 11 dashboard + PART 1 registry with
 * PART 12 search/filters + PART 9 budget tracking). The dashboard and the
 * registry list are independent data sources — each renders its own
 * loading/error state (same split as the Committees hub).
 */
export default function FinancePage() {
  const {
    dashboard,
    budgets,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useFinanceDashboard();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ProposalStatus | "all">("all");
  const [department, setDepartment] = useState("");
  const [vendor, setVendor] = useState("");
  const [financialYear, setFinancialYear] = useState("");
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
  } = useProposals({
    pageSize: DEFAULT_PROPOSAL_PAGE_SIZE,
    search,
    status: status === "all" ? null : status,
    department: department.trim() || null,
    vendor: vendor.trim() || null,
    financialYear: financialYear || null,
  });

  // Pick up a message handed over by another page (e.g. "proposal deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: ProposalSaveResult) => {
      setModalOpen(false);
      refresh();
      refreshDashboard();
      show(
        "success",
        `“${result.proposal.title}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
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
    setStatus("all");
    setDepartment("");
    setVendor("");
    setFinancialYear("");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Finance" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Finance &amp; Procurement</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} proposal${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search number, title, vendor…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={loading || refreshing || dashboardLoading}
                  aria-label="Refresh finance"
                  title="Refresh"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                    aria-hidden="true"
                  />
                </button>
                <Link
                  href="/finance/vendors"
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <Truck className="h-4 w-4" aria-hidden="true" /> Vendors
                </Link>
                <Link
                  href="/finance/assets"
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <Package className="h-4 w-4" aria-hidden="true" /> Asset Register
                </Link>
                <button
                  type="button"
                  onClick={() => setModalOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Proposal
                </button>
              </div>
            </div>
          </div>

          {/* PART 11 dashboard */}
          <div className="mt-6">
            {dashboardError ? (
              <p
                role="alert"
                className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                Could not load the finance dashboard — {dashboardError}
              </p>
            ) : dashboardLoading || !dashboard ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
                {Array.from({ length: 7 }, (_, index) => (
                  <CardSkeleton key={index} lines={2} />
                ))}
              </div>
            ) : (
              <FinanceDashboardCards dashboard={dashboard} />
            )}
          </div>

          {/* PART 12 filters */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as ProposalStatus | "all")}
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              <option value="all">All statuses</option>
              {PROPOSAL_STATUSES.map((option) => (
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
              value={vendor}
              onChange={(event) => setVendor(event.target.value)}
              placeholder="Vendor"
              aria-label="Filter by vendor"
              className={`${INPUT_CLASS} w-40`}
            />
            <select
              value={financialYear}
              onChange={(event) => setFinancialYear(event.target.value)}
              aria-label="Filter by financial year"
              className={SELECT_CLASS}
            >
              <option value="">All financial years</option>
              {financialYearOptions().map((option) => (
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
                title="Could not load proposals"
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
                <ProposalTable proposals={items} loading={loading} />
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
                title="No matching proposals"
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
                title="No purchase proposals yet"
                description="Create your first proposal — link vendors, quotations and the procurement committee, then track orders, bills and assets."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Proposal
                  </button>
                }
              />
            )}
          </div>

          {/* PART 9 budget tracking */}
          <div className="mt-6">
            <BudgetTrackingPanel lines={budgets} />
          </div>
        </main>
      </div>

      <ProposalModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
