"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { ObjectTable } from "@/components/features/objects/ObjectTable";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  CreateObjectModal,
  type ObjectSaveResult,
} from "@/components/features/objects/CreateObjectModal";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useObjects } from "@/hooks/useObjects";
import { DEFAULT_PAGE_SIZE, SEARCH_WINDOW_SIZE } from "@/lib/objects/constants";
import { consumeFlash } from "@/lib/objects/flash";

export default function ObjectsPage() {
  const [search, setSearch] = useState("");
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
    searchTruncated,
    setPage,
    refresh,
  } = useObjects({ pageSize: DEFAULT_PAGE_SIZE, search });

  // Pick up a message handed over by another page (e.g. "object deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: ObjectSaveResult) => {
      setModalOpen(false);
      refresh();
      show("success", `“${result.object.title}” created successfully.`);
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Objects" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Objects</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : searchActive
                      ? `${total} match${total === 1 ? "" : "es"} for “${search.trim()}”`
                      : `${total} object${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar value={search} onChange={setSearch} busy={isSearching} />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh objects"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Object
                </button>
              </div>
            </div>
          </div>

          {searchTruncated ? (
            <p className="mt-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              Searching the most recent {SEARCH_WINDOW_SIZE} objects. Server-side search is
              required to cover the full dataset.
            </p>
          ) : null}

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load objects"
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
                <ObjectTable objects={items} loading={loading} refreshing={refreshing} />
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
            ) : searchActive ? (
              <EmptyState
                title="No matching objects"
                description={`Nothing matches “${search.trim()}”. Try a different term or clear the search.`}
                action={
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    Clear search
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="No objects yet"
                description="Create your first object to start building the knowledge graph."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Object
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <CreateObjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
