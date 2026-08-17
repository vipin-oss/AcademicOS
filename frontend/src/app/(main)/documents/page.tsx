"use client";

import { useCallback, useEffect, useState } from "react";
import { Filter, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { cn } from "@/lib/utils";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { DocumentTable } from "@/components/features/documents/DocumentTable";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  UploadModal,
  type DocumentSaveResult,
} from "@/components/features/documents/UploadModal";
import { MultiFileUpload } from "@/components/features/documents/MultiFileUpload";
import { SimpleUpload } from "@/components/features/documents/SimpleUpload";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useDocuments } from "@/hooks/useDocuments";
import { DEFAULT_DOC_PAGE_SIZE, SEARCH_WINDOW_SIZE } from "@/lib/documents/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { DocumentStatus, DocumentTypeValue } from "@/types";

const TYPE_OPTIONS: (DocumentTypeValue | "all")[] = [
  "all",
  "pdf",
  "docx",
  "xlsx",
  "pptx",
  "txt",
  "zip",
  "image",
  "video",
  "unknown",
];

const STATUS_OPTIONS: (DocumentStatus | "all")[] = ["all", "draft", "active", "archived"];

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState<DocumentTypeValue | "all">("all");
  const [status, setStatus] = useState<DocumentStatus | "all">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState<"single" | "multi">("single");
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
  } = useDocuments({ pageSize: DEFAULT_DOC_PAGE_SIZE, search, type, status });

  // Pick up a message handed over by another page (e.g. "document deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: DocumentSaveResult) => {
      setModalOpen(false);
      refresh();
      show("success", `“${result.document.title}” ${result.mode === "edit" ? "updated" : "uploaded"} successfully.`);
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;
  const filtering = searchActive || type !== "all" || status !== "all";

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Documents" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Documents</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} document${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar value={search} onChange={setSearch} busy={isSearching} placeholder="Search documents…" />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh documents"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> Upload Document
                </button>
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={type}
              onChange={(event) => setType(event.target.value as DocumentTypeValue | "all")}
              aria-label="Filter by type"
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
            >
              {TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === "all" ? "All types" : option.toUpperCase()}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as DocumentStatus | "all")}
              aria-label="Filter by status"
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === "all" ? "All statuses" : option[0].toUpperCase() + option.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {searchTruncated ? (
            <p className="mt-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              Searching the most recent {SEARCH_WINDOW_SIZE} documents. Server-side search is
              required to cover the full dataset.
            </p>
          ) : null}

          {/* Upload section */}
          <div className="mt-6">
            <div className="mb-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setUploadMode("single")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  uploadMode === "single"
                    ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                )}
              >
                Single File
              </button>
              <button
                type="button"
                onClick={() => setUploadMode("multi")}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  uploadMode === "multi"
                    ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                )}
              >
                Multiple Files
              </button>
            </div>

            {uploadMode === "single" ? (
              <SimpleUpload onUploaded={() => refresh()} />
            ) : (
              <MultiFileUpload onBatchComplete={() => refresh()} />
            )}
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load documents"
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
                <DocumentTable documents={items} loading={loading} refreshing={refreshing} />
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
                title="No matching documents"
                description="Nothing matches your search and filters. Try different terms or clear them."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setType("all");
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
                title="No documents yet"
                description="Upload your first document to start building the knowledge base."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> Upload Document
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <UploadModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
