"use client";

import { useCallback, useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { VendorTable } from "@/components/features/finance/VendorTable";
import {
  VendorModal,
  type VendorSaveResult,
} from "@/components/features/finance/VendorModal";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useVendors } from "@/hooks/useVendors";
import { deleteVendor } from "@/lib/api/finance";
import { toErrorMessage } from "@/lib/api/client";
import { DEFAULT_VENDOR_PAGE_SIZE } from "@/lib/finance/constants";
import type { VendorResponse } from "@/types";

/**
 * PART 3 vendor registry: GST/PAN identities, contact details and bank
 * details, with the per-vendor spend stats computed server-side.
 */
export default function VendorsPage() {
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<VendorResponse | null>(null);
  const [deleting, setDeleting] = useState<VendorResponse | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
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
    searchActive,
    setPage,
    refresh,
  } = useVendors({ pageSize: DEFAULT_VENDOR_PAGE_SIZE, search });

  const handleSaved = useCallback(
    (result: VendorSaveResult) => {
      setModalOpen(false);
      setEditing(null);
      refresh();
      show(
        "success",
        `“${result.vendor.name}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
      );
    },
    [refresh, show],
  );

  const handleEdit = useCallback((vendor: VendorResponse) => {
    setEditing(vendor);
    setModalOpen(true);
  }, []);

  const handleDeleteRequest = useCallback((vendor: VendorResponse) => {
    setDeleteError(null);
    setDeleting(vendor);
  }, []);

  const handleDelete = useCallback(async () => {
    if (!deleting || deleteBusy) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteVendor(deleting.id);
      setDeleting(null);
      setDeleteBusy(false);
      refresh();
      show("success", `“${deleting.name}” was deleted.`);
    } catch (err) {
      setDeleteBusy(false);
      setDeleteError(toErrorMessage(err, "Failed to delete this vendor."));
    }
  }, [deleting, deleteBusy, refresh, show]);

  const showTable = loading || items.length > 0;

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
              { label: "Vendors" },
            ]}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Vendors</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : searchActive
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} vendor${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search name, GST, PAN, contact…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh vendors"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Vendor
                </button>
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load vendors"
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
                <VendorTable
                  vendors={items}
                  loading={loading}
                  onEdit={handleEdit}
                  onDelete={handleDeleteRequest}
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
            ) : searchActive ? (
              <EmptyState
                title="No matching vendors"
                description="Nothing matches your search. Try a different name, GST number or contact."
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
                title="No vendors yet"
                description="Register your first vendor — GST and PAN identities are validated and de-duplicated."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(null);
                      setModalOpen(true);
                    }}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Vendor
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <VendorModal
        open={modalOpen}
        vendor={editing}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        onSaved={handleSaved}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete vendor?"
        description={
          deleting ? (
            <>
              <span className="font-medium text-[var(--text-primary)]">“{deleting.name}”</span>{" "}
              will be permanently removed. Quotations, orders and bills that reference this
              vendor keep their recorded names. This action cannot be undone.
            </>
          ) : (
            ""
          )
        }
        confirmLabel="Delete"
        loadingLabel="Deleting…"
        loading={deleteBusy}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => {
          if (!deleteBusy) {
            setDeleting(null);
            setDeleteError(null);
          }
        }}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
