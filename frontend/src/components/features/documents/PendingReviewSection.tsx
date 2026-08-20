"use client";

/**
 * PendingReviewSection — shows all pending review fields for a document.
 *
 * Simplified table view: Field | Value | Confidence | Actions.
 * "Confirm All" button at top for high-confidence items.
 * Individual Edit/Reject on hover/click.
 */

import { useCallback, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  XCircle,
  Edit3,
  Loader2,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api/client";
import type { PendingReviewItemResponse } from "@/lib/api/documentIntake";
import { friendlyFieldName } from "@/lib/fieldLabels";

function confidenceDot(c: number | null): { color: string; title: string } {
  if (c === null) return { color: "bg-gray-300", title: "" };
  if (c >= 0.9) return { color: "bg-emerald-500", title: "High confidence" };
  if (c >= 0.75) return { color: "bg-amber-500", title: "Medium confidence" };
  return { color: "bg-red-500", title: "Low confidence" };
}

function ReviewRow({
  item,
  onResolved,
}: {
  item: PendingReviewItemResponse;
  onResolved: (claimId: string) => void;
}) {
  const [acting, setActing] = useState(false);
  const [resolved, setResolved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.display_value);

  const conf = confidenceDot(item.confidence);
  const hasValue = item.display_value && item.display_value.trim() !== "";
  const fieldName = friendlyFieldName(item.predicate_id);

  const handleConfirm = useCallback(async () => {
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/approve`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, onResolved]);

  const handleReject = useCallback(async () => {
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/reject`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, onResolved]);

  const handleEditSave = useCallback(async () => {
    if (!editValue.trim()) return;
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/correct`, {
        raw_value: editValue.trim(),
        notes: "Manual correction",
      });
      setEditing(false);
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, editValue, onResolved]);

  if (resolved) {
    return (
      <tr className="bg-emerald-50">
        <td className="px-3 py-2 text-xs text-emerald-700" colSpan={4}>
          <CheckCircle2 className="inline h-3.5 w-3.5 mr-1" />{fieldName} saved
        </td>
      </tr>
    );
  }

  return (
    <tr className="group hover:bg-[var(--bg-hover)] transition-colors">
      {/* Field name */}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${conf.color}`} title={conf.title} aria-label={conf.title} />
          <span className="text-sm font-medium text-[var(--text-primary)]">{fieldName}</span>
            {item.status === "auto_suggested" && (
            <Sparkles className="h-3 w-3 text-blue-400" />
          )}
        </div>
      </td>

      {/* Value */}
      <td className="px-3 py-2.5">
        {editing ? (
          <div className="flex gap-1.5">
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="flex-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleEditSave();
                if (e.key === "Escape") { setEditing(false); setEditValue(item.display_value); }
              }}
              autoFocus
            />
            <button type="button" onClick={() => void handleEditSave()} disabled={acting}
              className="rounded bg-[var(--accent)] px-2 py-1 text-xs text-white disabled:opacity-50">Save</button>
            <button type="button" onClick={() => { setEditing(false); setEditValue(item.display_value); }}
              className="rounded border border-[var(--border-subtle)] px-2 py-1 text-xs">Cancel</button>
          </div>
        ) : hasValue ? (
          <span className="text-sm text-[var(--text-primary)]">{item.display_value}</span>
        ) : (
          <span className="text-sm text-[var(--text-tertiary)] italic">Not found</span>
        )}
      </td>

      {/* Source evidence (compact) */}
      <td className="px-3 py-2.5 max-w-[200px]">
        {hasValue && item.source_text && item.source_text.trim() !== "" && !editing && (
          <span className="text-[11px] text-blue-600 font-mono truncate block" title={item.source_text}>
            &ldquo;{item.source_text.length > 50 ? item.source_text.slice(0, 50) + "..." : item.source_text}&rdquo;
          </span>
        )}
      </td>

      {/* Actions */}
      <td className="px-3 py-2.5 text-right">
        {editing ? null : (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button type="button" onClick={() => void handleConfirm()} disabled={acting}
              className="rounded-md bg-emerald-100 p-1.5 text-emerald-700 hover:bg-emerald-200 disabled:opacity-50" title="Confirm">
              <CheckCircle2 className="h-3.5 w-3.5" />
            </button>
            <button type="button" onClick={() => { setEditing(true); setEditValue(item.display_value); }} disabled={acting}
              className="rounded-md bg-[var(--bg-hover)] p-1.5 text-[var(--text-secondary)] hover:bg-[var(--border-subtle)] disabled:opacity-50" title="Edit">
              <Edit3 className="h-3.5 w-3.5" />
            </button>
            <button type="button" onClick={() => void handleReject()} disabled={acting}
              className="rounded-md bg-red-50 p-1.5 text-red-600 hover:bg-red-100 disabled:opacity-50" title="Not applicable">
              <XCircle className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

export interface PendingReviewSectionProps {
  documentId: string;
  documentTitle: string;
  items: PendingReviewItemResponse[];
  loading: boolean;
  onItemResolved: () => void;
}

export function PendingReviewSection({
  documentId,
  documentTitle,
  items,
  loading,
  onItemResolved,
}: PendingReviewSectionProps) {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState(true);
  const [confirmingAll, setConfirmingAll] = useState(false);
  const [createdRecords, setCreatedRecords] = useState<Array<{id: string; type: string; title: string}>>([]);

  const handleResolved = useCallback(
    (claimId: string) => {
      setResolvedIds((prev) => new Set(prev).add(claimId));
      onItemResolved();
    },
    [onItemResolved],
  );

  const pendingItems = items.filter((item) => !resolvedIds.has(item.claim_id));

  const handleConfirmAll = useCallback(async () => {
    setConfirmingAll(true);
    try {
      const result: any = await api.post(`/documents/${documentId}/confirm-all-high-confidence`, undefined, {
        query: { min_confidence: 0.9 },
      });
      const highConfIds = pendingItems
        .filter((item) => (item.confidence ?? 0) >= 0.9)
        .map((item) => item.claim_id);
      setResolvedIds((prev) => {
        const next = new Set(prev);
        highConfIds.forEach((id) => next.add(id));
        return next;
      });
      if (result?.records_created?.length > 0) {
        setCreatedRecords(result.records_created);
      }
      onItemResolved();
    } catch { /* silent */ } finally { setConfirmingAll(false); }
  }, [documentId, pendingItems, onItemResolved]);

  if (loading) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
          <span className="text-sm text-amber-800">Loading review items...</span>
        </div>
      </div>
    );
  }

  if (pendingItems.length === 0) {
    if (resolvedIds.size > 0) {
      const TYPE_LABELS: Record<string, string> = {
        event: "Event", publication: "Publication", project: "Research Project", committee: "Committee",
      };
      const TYPE_LINKS: Record<string, string> = {
        event: "/events/", publication: "/publications/", project: "/research/projects/", committee: "/committees/",
      };
      return (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-sm font-semibold text-emerald-900">All reviewed</p>
              {createdRecords.length > 0 ? (
                <div className="mt-1 space-y-1">
                  {createdRecords.map((rec) => (
                    <p key={rec.id} className="text-xs text-emerald-700">
                      Recorded as {TYPE_LABELS[rec.type] ?? rec.type}:{" "}
                      <Link href={`${TYPE_LINKS[rec.type] ?? "/records/"}${encodeURIComponent(rec.id)}`}
                        className="font-semibold underline hover:text-emerald-900">
                        {rec.title || "View"}
                      </Link>
                    </p>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-700">
                  Information saved.{" "}
                  <Link href={`/documents/${encodeURIComponent(documentId)}`} className="underline hover:text-emerald-900">
                    View document
                  </Link>
                </p>
              )}
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  const highConfCount = pendingItems.filter((i) => (i.confidence ?? 0) >= 0.9).length;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50" id="review-section">
      {/* Header */}
      <div className="flex w-full items-center gap-2 border-b border-amber-200 px-4 py-3">
        <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-amber-900">
            {pendingItems.length} {pendingItems.length === 1 ? "field" : "fields"} need your review
          </h2>
        </div>
        {highConfCount > 0 && (
          <button type="button" onClick={() => void handleConfirmAll()} disabled={confirmingAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 shrink-0">
            {confirmingAll ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            {confirmingAll ? "Confirming..." : `Confirm All (${highConfCount})`}
          </button>
        )}
        <button type="button" onClick={() => setExpanded((v) => !v)}
          className="p-1 rounded hover:bg-amber-100 transition-colors shrink-0">
          {expanded ? <ChevronDown className="h-4 w-4 text-amber-600" /> : <ChevronRight className="h-4 w-4 text-amber-600" />}
        </button>
      </div>

      {/* Table */}
      {expanded && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-amber-200 text-xs text-amber-700">
                <th className="px-3 py-2 text-left font-medium">Field</th>
                <th className="px-3 py-2 text-left font-medium">Extracted Value</th>
                <th className="px-3 py-2 text-left font-medium">Source</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-100">
              {pendingItems.map((item) => (
                <ReviewRow key={item.claim_id} item={item} onResolved={handleResolved} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
