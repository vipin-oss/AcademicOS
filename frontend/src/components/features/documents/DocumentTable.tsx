"use client";

/**
 * Documents table with bulk selection support.
 * Columns collapse progressively (sm/md/lg) so the table
 * never scrolls sideways on a phone — the name cell keeps a compact secondary
 * line instead.
 */

import { useCallback, useState } from "react";
import { Trash2, FolderInput, Tag, Loader2, X, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DocumentResponse } from "@/types";
import { DocumentRow } from "./DocumentRow";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { api } from "@/lib/api/client";

interface BulkActionsBarProps {
  selectedCount: number;
  onClear: () => void;
  onDelete: () => void;
  deleting: boolean;
}

function BulkActionsBar({ selectedCount, onClear, onDelete, deleting }: BulkActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-[var(--accent)] bg-[var(--accent-subtle)] px-4 py-2.5">
      <span className="text-sm font-medium text-[var(--accent)]">
        {selectedCount} selected
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDelete}
          disabled={deleting}
          className="inline-flex items-center gap-1.5 rounded-lg bg-red-100 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
        >
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
      <button
        type="button"
        onClick={onClear}
        className="ml-auto rounded p-1 hover:bg-[var(--bg-hover)]"
        aria-label="Clear selection"
      >
        <X className="h-4 w-4 text-[var(--text-tertiary)]" />
      </button>
    </div>
  );
}

interface DeleteConfirmDialogProps {
  open: boolean;
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
  deleting: boolean;
  result: { success: number; failed: number } | null;
}

function DeleteConfirmDialog({ open, count, onConfirm, onCancel, deleting, result }: DeleteConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={(e) => { if (e.target === e.currentTarget && !deleting) onCancel(); }}>
      <div className="w-full max-w-sm rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-2xl">
        {result ? (
          <>
            <div className="flex items-center gap-3 mb-4">
              {result.failed > 0 ? (
                <AlertTriangle className="h-6 w-6 text-amber-500" />
              ) : (
                <Trash2 className="h-6 w-6 text-emerald-500" />
              )}
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                {result.failed > 0 ? "Partial Success" : "Deleted"}
              </h3>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              {result.success > 0 && `${result.success} document${result.success !== 1 ? "s" : ""} deleted.`}
              {result.failed > 0 && ` ${result.failed} failed.`}
            </p>
            <button
              type="button"
              onClick={onCancel}
              className="w-full rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
            >
              Done
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="h-6 w-6 text-red-500" />
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                Delete {count} document{count !== 1 ? "s" : ""}?
              </h3>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mb-6">
              This action cannot be undone. The documents will be permanently removed.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={onCancel}
                disabled={deleting}
                className="flex-1 rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={deleting}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function DocumentTable({
  documents,
  loading = false,
  refreshing = false,
  onDocumentsChanged,
}: {
  documents: DocumentResponse[];
  loading?: boolean;
  /** Background reload: keep rows visible, just dim them slightly. */
  refreshing?: boolean;
  onDocumentsChanged?: () => void;
}) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleteResult, setDeleteResult] = useState<{ success: number; failed: number } | null>(null);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    }
  }, [documents, selectedIds.size]);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const handleBulkDelete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    setDeleteResult(null);
    
    const ids = Array.from(selectedIds);
    let success = 0;
    let failed = 0;
    
    // Delete one by one, tracking success/failure
    for (const id of ids) {
      try {
        await api.delete(`/documents/${id}`);
        success++;
      } catch {
        failed++;
      }
    }
    
    setDeleting(false);
    setDeleteResult({ success, failed });
    
    if (success > 0) {
      clearSelection();
      onDocumentsChanged?.();
    }
  }, [selectedIds, clearSelection, onDocumentsChanged]);

  const handleConfirmClose = useCallback(() => {
    setConfirmOpen(false);
    setDeleteResult(null);
  }, []);

  const allSelected = documents.length > 0 && selectedIds.size === documents.length;

  return (
    <div className="space-y-2">
      {/* Bulk actions bar */}
      <BulkActionsBar
        selectedCount={selectedIds.size}
        onClear={clearSelection}
        onDelete={() => setConfirmOpen(true)}
        deleting={deleting}
      />
      
      {/* Delete confirmation dialog */}
      <DeleteConfirmDialog
        open={confirmOpen}
        count={selectedIds.size}
        onConfirm={() => void handleBulkDelete()}
        onCancel={handleConfirmClose}
        deleting={deleting}
        result={deleteResult}
      />

      <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Documents</caption>
            <thead>
              <tr className="text-[var(--text-tertiary)]">
                <th scope="col" className="w-10 px-2 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    aria-label="Select all documents"
                    className="h-4 w-4 rounded border-[var(--border-subtle)] text-[var(--accent)] focus:ring-[var(--accent)]"
                  />
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Document Name
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                  Linked Object
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium sm:table-cell">
                  Type
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                  Size
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium md:table-cell">
                  Uploaded By
                </th>
                <th scope="col" className="hidden px-4 py-3 font-medium lg:table-cell">
                  Upload Date
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody
              className={cn(
                "transition-opacity duration-150",
                refreshing && !loading && "opacity-60",
              )}
              aria-busy={loading || refreshing}
            >
              {loading ? (
                <TableSkeleton rows={6} cols={9} />
              ) : (
                documents.map((document) => (
                  <DocumentRow
                    key={document.id}
                    document={document}
                    selected={selectedIds.has(document.id)}
                    onToggleSelect={toggleSelect}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
