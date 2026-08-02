"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  GrantModal,
  type GrantSaveResult,
} from "@/components/features/research/GrantModal";
import { GrantTable } from "@/components/features/research/GrantTable";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useGrants } from "@/hooks/useGrants";
import { DEFAULT_GRANT_PAGE_SIZE } from "@/lib/research/constants";
import { consumeFlash } from "@/lib/objects/flash";
import { titleCase } from "@/lib/utils";
import type { ResearchObjectStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const STATUSES: ResearchObjectStatus[] = ["draft", "active", "archived"];

/** The grants registry (PART 3): searchable, server-side paginated. */
export default function GrantsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ResearchObjectStatus | "all">("all");
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
    setPage,
    refresh,
  } = useGrants({
    pageSize: DEFAULT_GRANT_PAGE_SIZE,
    search,
    status: status === "all" ? null : status,
  });

  // Pick up a message handed over by another page (e.g. "grant deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: GrantSaveResult) => {
      setModalOpen(false);
      refresh();
      show(
        "success",
        `“${result.grant.title}” ${result.mode === "edit" ? "updated" : "registered"} successfully.`,
      );
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;
  const filtering = search.trim().length > 0 || status !== "all";

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Research", href: "/research" },
              { label: "Grants" },
            ]}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Grants</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} grant${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search title or grant number…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={status}
                  onChange={(event) =>
                    setStatus(event.target.value as ResearchObjectStatus | "all")
                  }
                  aria-label="Filter by status"
                  className={SELECT_CLASS}
                >
                  <option value="all">All statuses</option>
                  {STATUSES.map((option) => (
                    <option key={option} value={option}>
                      {titleCase(option)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh grants"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Grant
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load grants"
                description={error}
                action={
                  <button
                    type="button"
                    onClick={refresh}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
                  </button>
                }
              />
            ) : showTable ? (
              <>
                <GrantTable grants={items} loading={loading} />
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
                title="No matching grants"
                description="Nothing matches your search and filters. Try different terms or clear them."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setStatus("all");
                    }}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    Clear filters
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="No grants yet"
                description="Register your first grant — link the sanctioning agency and funded projects, then track installments and expenditure."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Grant
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <GrantModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
