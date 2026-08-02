"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import {
  AgencyModal,
  type AgencySaveResult,
} from "@/components/features/research/AgencyModal";
import { AgencyTable } from "@/components/features/research/AgencyTable";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useAgencies } from "@/hooks/useAgencies";
import { deleteAgency } from "@/lib/api/research";
import { toErrorMessage } from "@/lib/api/client";
import { DEFAULT_AGENCY_PAGE_SIZE } from "@/lib/research/constants";
import { consumeFlash } from "@/lib/objects/flash";
import { titleCase } from "@/lib/utils";
import type { AgencyResponse, ResearchObjectStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const STATUSES: ResearchObjectStatus[] = ["draft", "active", "archived"];

/** The funding-agency registry (PART 2): DST, CSIR, UGC, ICSSR, … */
export default function AgenciesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ResearchObjectStatus | "all">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AgencyResponse | null>(null);
  const [deletingAgency, setDeletingAgency] = useState<AgencyResponse | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
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
  } = useAgencies({
    pageSize: DEFAULT_AGENCY_PAGE_SIZE,
    search,
    status: status === "all" ? null : status,
  });

  // Pick up a message handed over by another page.
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: AgencySaveResult) => {
      setModalOpen(false);
      setEditing(null);
      refresh();
      show(
        "success",
        `“${result.agency.name}” ${result.mode === "edit" ? "updated" : "registered"} successfully.`,
      );
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!deletingAgency || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAgency(deletingAgency.id);
      setDeletingAgency(null);
      refresh();
      show("success", `“${deletingAgency.name}” was deleted.`);
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this agency."));
    } finally {
      setDeleting(false);
    }
  }, [deletingAgency, deleting, refresh, show]);

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
              { label: "Funding Agencies" },
            ]}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Funding Agencies</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} agenc${total === 1 ? "y" : "ies"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search agency, scheme, contact…"
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
                  aria-label="Refresh agencies"
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
                  onClick={() => {
                    setEditing(null);
                    setModalOpen(true);
                  }}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Agency
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load agencies"
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
                <AgencyTable
                  agencies={items}
                  loading={loading}
                  onEdit={(agency) => {
                    setEditing(agency);
                    setModalOpen(true);
                  }}
                  onDelete={(agency) => {
                    setDeleteError(null);
                    setDeletingAgency(agency);
                  }}
                />
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
                title="No matching agencies"
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
                title="No funding agencies yet"
                description="Register the agencies you apply to — DST, CSIR, UGC, ICSSR, DBT, ICMR, AICTE, SERB, state research foundations — then link them to projects and grants."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(null);
                      setModalOpen(true);
                    }}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Agency
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <AgencyModal
        open={modalOpen}
        agency={editing}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        onSaved={handleSaved}
      />
      <ConfirmDialog
        open={deletingAgency != null}
        title="Delete agency?"
        description={
          <>
            <span className="font-medium text-[var(--text-primary)]">
              “{deletingAgency?.name}”
            </span>{" "}
            will be permanently removed from the registry. Projects and grants that link to it
            are kept. This action cannot be undone.
          </>
        }
        confirmLabel="Delete"
        loadingLabel="Deleting…"
        loading={deleting}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => {
          if (!deleting) {
            setDeletingAgency(null);
            setDeleteError(null);
          }
        }}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
