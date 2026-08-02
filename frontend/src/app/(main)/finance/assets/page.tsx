"use client";

import { useState } from "react";
import { Filter, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { AssetRegisterTable } from "@/components/features/finance/AssetRegisterTable";
import { useAssetRegister } from "@/hooks/useAssetRegister";
import {
  ASSET_CATEGORIES,
  ASSET_STATUSES,
  DEFAULT_ASSET_PAGE_SIZE,
} from "@/lib/finance/constants";
import type { AssetCategory, AssetStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * PART 8 asset register — every asset recorded on any purchase proposal,
 * searchable by ID/item/serial and filterable by category and status.
 */
export default function AssetRegisterPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<AssetCategory | "all">("all");
  const [status, setStatus] = useState<AssetStatus | "all">("all");

  const {
    items,
    total,
    page,
    pageSize,
    loading,
    refreshing,
    error,
    searchActive,
    filterActive,
    setPage,
    refresh,
  } = useAssetRegister({
    pageSize: DEFAULT_ASSET_PAGE_SIZE,
    search,
    category: category === "all" ? null : category,
    status: status === "all" ? null : status,
  });

  const showTable = loading || items.length > 0;
  const filtering = searchActive || filterActive;

  const clearFilters = () => {
    setSearch("");
    setCategory("all");
    setStatus("all");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Finance", href: "/finance" },
              { label: "Asset Register" },
            ]}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Asset Register</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} asset${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={refreshing && !loading}
                placeholder="Search asset ID, item, serial…"
              />
              <button
                type="button"
                onClick={refresh}
                disabled={loading || refreshing}
                aria-label="Refresh asset register"
                title="Refresh"
                className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
              </button>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value as AssetCategory | "all")}
              aria-label="Filter by category"
              className={SELECT_CLASS}
            >
              <option value="all">All categories</option>
              {ASSET_CATEGORIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as AssetStatus | "all")}
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              <option value="all">All statuses</option>
              {ASSET_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load the asset register"
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
                <AssetRegisterTable items={items} loading={loading} />
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
                title="No matching assets"
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
                title="No assets yet"
                description="Assets appear here when they are recorded on a purchase proposal's Assets section."
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
