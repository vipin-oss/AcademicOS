"use client";

import { useCallback, useEffect, useState } from "react";
import { Filter, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { DocumentTable } from "@/components/features/documents/DocumentTable";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { FolderSidebar } from "@/components/features/documents/FolderSidebar";
import { SimpleUpload } from "@/components/features/documents/SimpleUpload";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useDocuments } from "@/hooks/useDocuments";
import { DEFAULT_DOC_PAGE_SIZE, SEARCH_WINDOW_SIZE } from "@/lib/documents/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { DocumentStatus, DocumentTypeValue } from "@/types";

const TYPE_OPTIONS: (DocumentTypeValue | "all")[] = [
  "all", "pdf", "docx", "xlsx", "pptx", "txt", "zip", "image", "video", "unknown",
];
const STATUS_OPTIONS: (DocumentStatus | "all")[] = ["all", "draft", "active", "archived"];

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState<DocumentTypeValue | "all">("all");
  const [status, setStatus] = useState<DocumentStatus | "all">("all");
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [folderRefreshKey, setFolderRefreshKey] = useState(0);
  const { toast, show, dismiss } = useToast();

  const {
    items, total, page, pageSize, loading, refreshing, error,
    isSearching, searchActive, searchTruncated, setPage, refresh,
  } = useDocuments({ pageSize: DEFAULT_DOC_PAGE_SIZE, search, type, status });

  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

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
                {loading ? "Loading..." : error ? "Unavailable" : filtering
                  ? `${total} match${total === 1 ? "" : "es"}`
                  : `${total} document${total === 1 ? "" : "s"}`}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar value={search} onChange={setSearch} busy={isSearching} placeholder="Search documents..." />
              <div className="flex items-center gap-2">
                <button type="button" onClick={refresh} disabled={loading || refreshing}
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50">
                  <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>
          </div>

          {/* Upload — drag-drop with auto-analyze. This is the PRIMARY upload path. */}
          <div className="mt-4">
            <SimpleUpload onUploaded={() => refresh()} />
          </div>

          {/* Filters */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" /> Filters:
            </div>
            <select value={type} onChange={(e) => setType(e.target.value as DocumentTypeValue | "all")}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none">
              {TYPE_OPTIONS.map((o) => <option key={o} value={o}>{o === "all" ? "All types" : o.toUpperCase()}</option>)}
            </select>
            <select value={status} onChange={(e) => setStatus(e.target.value as DocumentStatus | "all")}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none">
              {STATUS_OPTIONS.map((o) => <option key={o} value={o}>{o === "all" ? "All statuses" : o[0].toUpperCase() + o.slice(1)}</option>)}
            </select>
          </div>

          {searchTruncated && (
            <p className="mt-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              Searching the most recent {SEARCH_WINDOW_SIZE} documents.
            </p>
          )}

          {/* Main content: folder sidebar + document list */}
          <div className="mt-6 flex gap-6">
            <FolderSidebar
              selectedFolderId={selectedFolderId}
              onSelectFolder={setSelectedFolderId}
              onFoldersChanged={() => setFolderRefreshKey((k) => k + 1)}
            />

            <div className="flex-1 space-y-4">
              {error ? (
                <EmptyState title="Could not load documents" description={error}
                  action={<button type="button" onClick={refresh}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]">
                    <RefreshCw className="h-4 w-4" /> Try again</button>} />
              ) : showTable ? (
                <>
                  <DocumentTable documents={items} loading={loading} refreshing={refreshing} onDocumentsChanged={refresh} />
                  {!loading && (
                    <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} disabled={refreshing} />
                  )}
                </>
              ) : filtering ? (
                <EmptyState title="No matching documents"
                  description="Nothing matches your search and filters."
                  action={<button type="button" onClick={() => { setSearch(""); setType("all"); setStatus("all"); }}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
                    Clear filters</button>} />
              ) : (
                <EmptyState title="No documents yet"
                  description="Drop files above to upload certificates, papers, and notices."
                  action={null} />
              )}
            </div>
          </div>
        </main>
      </div>

      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
